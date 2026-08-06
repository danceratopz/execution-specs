"""
A hive based simulator that makes clients full sync fixture blocks.

Where `consume rlp` hands a client its blocks through a client specific
offline import mode, and `consume engine` hands them over one
`engine_newPayload` call at a time, this simulator makes the client
fetch them itself, from a mock peer speaking the production devp2p
protocols.

The control plane and the data plane are deliberately separate:

- The control plane is the Engine API. A post-merge client does not
  choose its own head, so it is told which block to sync to. That takes
  one `engine_newPayload` for the head block, which gives the client the
  header, and one `engine_forkchoiceUpdated` naming that head.
- The data plane is devp2p. Every block before the head is downloaded
  from the mock peer over RLPx and executed by the client's full sync
  path.

Because only the blocks before the head travel over devp2p, a fixture
whose chain is a single block would exercise no sync at all, and is
skipped by default. Removing that limitation means having the fill step
emit one extra block per test purely as a sync target, which is what the
existing `blockchain_test_sync` format already does.
"""

import time

import pytest
from hive.client import Client

from execution_testing.devp2p.chain import Chain
from execution_testing.devp2p.peer import MockPeer
from execution_testing.fixtures import BlockchainEngineXFixture
from execution_testing.fixtures.blockchain import FixtureHeader
from execution_testing.logging import get_logger
from execution_testing.rpc import (
    EngineRPC,
    EthRPC,
    ForkchoiceUpdateTimeoutError,
)
from execution_testing.rpc.rpc_types import ForkchoiceState, PayloadStatusEnum

from ..helpers.exceptions import (
    GenesisBlockMismatchExceptionError,
    LoggedError,
)
from ..helpers.timing import TimingData

logger = get_logger(__name__)


def test_blockchain_via_wirex(
    timing_data: TimingData,
    eth_rpc: EthRPC,
    engine_rpc: EngineRPC,
    client: Client,
    genesis_verified_clients: set[str],
    fixture: BlockchainEngineXFixture,
    genesis_header: FixtureHeader,
    chain: Chain,
    mock_peer: MockPeer,
    wirex_min_blocks: int,
    wirex_sync_timeout: float,
    wirex_poll_interval: float,
    wirex_announce_interval: float,
) -> None:
    """
    Make a client full sync one test's chain from the mock peer.

    The sequence is:

    1. Rewind the client to genesis, which is what makes the tests of a
       pre-allocation group independent of each other.
    2. Verify the client's genesis matches the group's, once per client.
    3. Deliver the head block over the Engine API so the client knows
       which chain to sync to, and name it in a forkchoice update.
    4. Wait for the client to download and execute the ancestors from the
       mock peer, polling the same forkchoice update until it is VALID.
    5. Check the client's head really is the expected block.
    """
    if any(not payload.valid() for payload in fixture.payloads):
        pytest.skip(
            "fixtures with invalid payloads cannot be served as a canonical "
            "chain: a full syncing client rejects the whole chain rather "
            "than reporting a per-block verdict"
        )
    if len(fixture.payloads) < wirex_min_blocks:
        pytest.skip(
            f"chain has {len(fixture.payloads)} block(s); at least "
            f"{wirex_min_blocks} are needed for any block to be transferred "
            "over devp2p rather than the Engine API"
        )

    head_payload = fixture.payloads[-1]
    head_hash = head_payload.params[0].block_hash
    genesis_state = ForkchoiceState(head_block_hash=genesis_header.block_hash)

    with timing_data.time("Rewind to genesis"):
        try:
            response = engine_rpc.forkchoice_updated_with_retry(
                forkchoice_state=genesis_state,
                forkchoice_version=fixture.payloads[
                    0
                ].forkchoice_updated_version,
                max_attempts=30,
                wait_fixed=1.0,
            )
        except ForkchoiceUpdateTimeoutError as error:
            raise LoggedError(
                f"Timed out rewinding the client to genesis: {error}"
            ) from None
        if response.payload_status.status != PayloadStatusEnum.VALID:
            raise LoggedError(
                "Unexpected status rewinding to genesis: "
                f"{response.payload_status.status}"
            )

        # The client's canonical head does not move back to genesis here:
        # a forkchoice update naming an ancestor of the current head is
        # accepted but not acted on. What the rewind does is make the
        # client willing to adopt a different chain from this genesis.

    if client.id not in genesis_verified_clients:
        with timing_data.time("Verify genesis"):
            genesis_block = eth_rpc.get_block_by_number(0)
            if genesis_block is None:
                raise LoggedError("Client returned no genesis block")
            if genesis_block["hash"] != str(genesis_header.block_hash):
                raise GenesisBlockMismatchExceptionError(
                    expected_header=genesis_header,
                    got_genesis_block=genesis_block,
                )
            genesis_verified_clients.add(client.id)

    expected_head = "0x" + chain.head.block_hash.hex()

    head_state = ForkchoiceState(
        head_block_hash=head_hash,
        safe_block_hash=genesis_header.block_hash,
        finalized_block_hash=genesis_header.block_hash,
    )

    def announce() -> None:
        """Tell the client which block to sync to."""
        engine_rpc.new_payload(
            *head_payload.params, version=head_payload.new_payload_version
        )
        engine_rpc.forkchoice_updated(
            forkchoice_state=head_state,
            payload_attributes=None,
            version=head_payload.forkchoice_updated_version,
        )

    with timing_data.time("Announce sync target"):
        logger.info(
            f"Announcing head block {chain.head.number} to trigger a sync "
            f"of {len(chain.blocks) - 1} ancestor block(s) over devp2p"
        )
        announce()

    with timing_data.time("Sync from peer"):
        # Wait by watching for the block rather than by repeating the
        # forkchoice update. A repeated update restarts the client's sync
        # cycle, and repeating it faster than a cycle takes prevents the
        # sync from ever finishing. The announcement is repeated on a much
        # slower cadence, as a consensus client would each slot, because a
        # client whose sync state was still settling may have ignored the
        # first one.
        deadline = time.monotonic() + wirex_sync_timeout
        next_announcement = time.monotonic() + wirex_announce_interval
        synced = False
        while time.monotonic() < deadline:
            if eth_rpc.get_block_by_hash(head_hash, full_txs=False):
                synced = True
                break
            if time.monotonic() >= next_announcement:
                logger.info("Re-announcing the sync target")
                announce()
                next_announcement = time.monotonic() + wirex_announce_interval
            time.sleep(wirex_poll_interval)
        if not synced:
            raise LoggedError(
                f"Client never imported the fixture head {expected_head} "
                f"within {wirex_sync_timeout}s. Peer transcript: "
                f"{mock_peer.statistics.transcript}"
            )

    with timing_data.time("Confirm head"):
        try:
            response = engine_rpc.forkchoice_updated_with_retry(
                forkchoice_state=head_state,
                forkchoice_version=head_payload.forkchoice_updated_version,
                max_attempts=10,
                wait_fixed=0.5,
            )
        except ForkchoiceUpdateTimeoutError as error:
            raise LoggedError(
                f"Client imported {expected_head} but never made it "
                f"canonical: {error}"
            ) from None
        if response.payload_status.status != PayloadStatusEnum.VALID:
            raise LoggedError(
                f"Client failed to sync to {expected_head}: "
                f"{response.payload_status.status}. Peer transcript: "
                f"{mock_peer.statistics.transcript}"
            )

    with timing_data.time("Verify head"):
        head_block = eth_rpc.get_block_by_number("latest")
        if head_block is None:
            raise LoggedError("Client returned no head block")
        if head_block["hash"] != expected_head:
            raise LoggedError(
                f"Client head is {head_block['hash']}, expected "
                f"{expected_head}"
            )

    statistics = mock_peer.statistics
    logger.info(
        f"Synced to block {chain.head.number}: peer served "
        f"{statistics.headers_served} header(s) in "
        f"{statistics.header_requests} request(s) and "
        f"{statistics.bodies_served} body/bodies in "
        f"{statistics.body_requests} request(s)"
    )
    if statistics.bodies_served == 0:
        raise LoggedError(
            "The client reached the expected head without downloading any "
            "block body from the peer, so nothing was verified over devp2p."
        )
    if statistics.receipt_requests:
        logger.warning(
            f"Client made {statistics.receipt_requests} receipt request(s), "
            "which this peer does not serve; the client may not be "
            "executing the blocks it downloads."
        )
