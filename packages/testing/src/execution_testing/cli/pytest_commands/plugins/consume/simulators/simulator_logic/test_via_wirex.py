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
skipped by default. Fixtures filled with the `--prepend-empty-block`
fill option have an empty block inserted between genesis and the test's
first block, so every chain is at least two blocks long and every
test's own blocks travel over devp2p.
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

    1. Verify the client's genesis matches the group's, once per client.
    2. Deliver the head block over the Engine API so the client knows
       which chain to sync to, and name it in a forkchoice update.
    3. Wait for the client to download and execute the ancestors from the
       mock peer, polling the same forkchoice update until it is VALID.
    4. Check the client's head really is the expected block.

    There is deliberately no rewind between tests. Every test's chain
    forks at genesis, so announcing the new head is all a consensus
    client would do, and a backwards forkchoice update is actively
    harmful to clients that act on it: nethermind moves its head back
    to genesis while its persisted state stays at the previous chain's
    tip, which lands it in a crash-recovery edge case where it fetches
    receipts instead of executing blocks (`BlockDownloader.
    ReceiptEdgeCase`); geth ignores the rewind entirely.

    Fixtures containing an intentionally invalid block are rejection
    tests: the peer serves the chain as-is and the client passes by
    refusing it - `engine_newPayload` for the head must answer INVALID
    once the ancestry is available over devp2p, and answering VALID
    fails the test. Only the fact of rejection is asserted: a devp2p
    peer observes acceptance or rejection, not error causes, so
    matching the fixture's specific exception over the wire is
    deliberately left for later. Fixtures whose invalid block cannot
    even be represented on the wire (declared hash inconsistent with
    the header) are skipped by the `chain` fixture.
    """
    if len(fixture.payloads) < wirex_min_blocks:
        pytest.skip(
            f"chain has {len(fixture.payloads)} block(s); at least "
            f"{wirex_min_blocks} are needed for any block to be transferred "
            "over devp2p rather than the Engine API"
        )

    head_payload = fixture.payloads[-1]
    head_hash = head_payload.params[0].block_hash

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

    if any(not payload.valid() for payload in fixture.payloads):
        with timing_data.time("Reject invalid chain"):
            deadline = time.monotonic() + wirex_sync_timeout
            next_announcement = time.monotonic() + wirex_announce_interval
            status: PayloadStatusEnum | None = None
            validation_error: object = None
            while time.monotonic() < deadline:
                # Once the ancestry has arrived over devp2p the client
                # can judge the head; until then it answers SYNCING (or
                # ACCEPTED if it merely stored the payload).
                payload_status = engine_rpc.new_payload(
                    *head_payload.params,
                    version=head_payload.new_payload_version,
                )
                status = payload_status.status
                validation_error = payload_status.validation_error
                if status in (
                    PayloadStatusEnum.INVALID,
                    PayloadStatusEnum.INVALID_BLOCK_HASH,
                ):
                    break
                if status == PayloadStatusEnum.VALID:
                    raise LoggedError(
                        f"Client accepted the invalid chain: head "
                        f"{expected_head} returned VALID but the fixture "
                        "expects the block to be rejected"
                    )
                if time.monotonic() >= next_announcement:
                    if not mock_peer.alive:
                        # A client may drop a peer that served it a bad
                        # chain; a real peer would simply redial.
                        logger.warning("Peer dropped mid-rejection; redialing")
                        mock_peer.reconnect(chain)
                    logger.info("Re-announcing the invalid sync target")
                    announce()
                    next_announcement = (
                        time.monotonic() + wirex_announce_interval
                    )
                time.sleep(wirex_poll_interval)
            if status not in (
                PayloadStatusEnum.INVALID,
                PayloadStatusEnum.INVALID_BLOCK_HASH,
            ):
                raise LoggedError(
                    f"Client never rejected the invalid head "
                    f"{expected_head} within {wirex_sync_timeout}s (last "
                    f"status: {status}). Peer transcript: "
                    f"{mock_peer.statistics.transcript}"
                )
        statistics = mock_peer.statistics
        logger.info(
            f"Client rejected the invalid head at block "
            f"{chain.head.number} with {status} "
            f"(validationError: {validation_error}) after the peer "
            f"served {statistics.headers_served} header(s) and "
            f"{statistics.bodies_served} body/bodies"
        )
        return

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
                if not mock_peer.alive:
                    # A mid-sync drop would otherwise strand the test
                    # peerless until its timeout; redial like a real
                    # peer would.
                    logger.warning("Peer dropped mid-sync; redialing")
                    mock_peer.reconnect(chain)
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
    non_empty_bodies = sum(
        1 for block in chain.blocks if block.transactions or block.withdrawals
    )
    if statistics.bodies_served == 0 and non_empty_bodies > 0:
        # A client may derive an empty body from its header (empty
        # transactions trie, empty withdrawals root) without asking the
        # peer, so zero body requests is only a finding when the chain
        # actually has bodies worth fetching.
        raise LoggedError(
            "The client reached the expected head without downloading any "
            f"of the chain's {non_empty_bodies} non-empty block bodies "
            "from the peer, so nothing was verified over devp2p."
        )
    if statistics.receipt_requests:
        logger.warning(
            f"Client made {statistics.receipt_requests} receipt request(s), "
            "which this peer does not serve; the client may not be "
            "executing the blocks it downloads."
        )
