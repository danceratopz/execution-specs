"""
Tests for the wirex wait loops of a head named by hash (pre-merge).

A blockchain_test_x path has no payload: its head is named in
`engine_forkchoiceUpdatedV1` alone and every block, the head included,
travels devp2p. The Engine and eth APIs and the peer are fakes and the
clock is a fake one, so a client that answers at its tenth announcement
is simulated in microseconds.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Collection, cast

import pytest

from execution_testing.base_types import Hash
from execution_testing.devp2p.chain import Chain, RlpBlock
from execution_testing.devp2p.peer import MockPeer, PeerStatistics
from execution_testing.exceptions import TransactionException
from execution_testing.fixtures.blockchain import FixtureHeader
from execution_testing.rpc import EngineRPC, EthRPC
from execution_testing.rpc.rpc_types import (
    ForkchoiceState,
    ForkchoiceUpdateResponse,
    PayloadAttributes,
    PayloadStatus,
    PayloadStatusEnum,
)

from ..simulators.helpers.exceptions import LoggedError
from ..simulators.helpers.timing import TimingData
from ..simulators.simulator_logic import test_via_wirex
from ..simulators.wirex.sync_targets import (
    RlpPathEntry,
    SyncPath,
    SyncTargetCase,
)

SYNC_TIMEOUT = 30.0
ANNOUNCE_INTERVAL = 1.0
POLL_INTERVAL = 0.005
NEVER = 1e9
"""An import time no test reaches."""

GENESIS_HASH = Hash(0x100)
INVALID = TransactionException.NONCE_MISMATCH_TOO_HIGH


class FakeClock:
    """A monotonic clock that only moves when told to."""

    def __init__(self) -> None:
        """Start at zero."""
        self.now = 0.0

    def monotonic(self) -> float:
        """Return the current fake time."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Advance the fake time instead of sleeping."""
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Replace the test body's clock with a fake one."""
    fake = FakeClock()
    monkeypatch.setattr(test_via_wirex, "time", fake)
    return fake


@dataclass
class _Genesis:
    """The genesis fields a chain and the runner read."""

    number: int = 0
    block_hash: Hash = GENESIS_HASH


def _block(number: int, parent: Hash) -> RlpBlock:
    """Return a non-empty block `number` with a state root of its own."""
    return RlpBlock(
        _header_rlp=b"",
        _body_rlp=b"",
        number=number,
        block_hash=Hash(number),
        parent_hash=parent,
        timestamp=12 * number,
        difficulty=0x20000,
        state_root=Hash(0x1000 + number),
        owes_body=True,
    )


def _case(length: int, invalid_head: bool = False) -> SyncTargetCase:
    """Return the path of a `length`-block chain, its head maybe invalid."""
    entries = []
    parent = GENESIS_HASH
    for number in range(1, length + 1):
        block = _block(number, parent)
        last = number == length
        entries.append(
            RlpPathEntry(
                block=block,
                validation_error=INVALID if invalid_head and last else None,
            )
        )
        parent = block.block_hash
    path = SyncPath(
        index=0,
        total=1,
        target=entries[-1],
        authored=tuple(entries),
        announces_scaffolding=False,
    )
    chain = Chain(
        cast(FixtureHeader, _Genesis()), [entry.block for entry in entries]
    )
    return SyncTargetCase(path=path, chain=chain)


@dataclass
class FakeEngine:
    """
    An Engine API that knows only forkchoice updates.

    `verdict` answers the n-th update; `latest_valid_hash` comes with
    every answer. A `newPayload` raises: a pre-merge head has none.
    """

    verdict: Callable[[int], PayloadStatusEnum] = (
        lambda _call: PayloadStatusEnum.SYNCING
    )
    latest_valid_hash: Hash | None = None
    states: list[ForkchoiceState] = field(default_factory=list)
    versions: list[int] = field(default_factory=list)
    times: list[float] = field(default_factory=list)
    clock: FakeClock | None = None
    eth: "FakeEth | None" = None

    def forkchoice_updated(
        self,
        forkchoice_state: ForkchoiceState,
        payload_attributes: PayloadAttributes | None = None,
        *,
        version: int,
    ) -> ForkchoiceUpdateResponse:
        """Record the update and answer this call's verdict."""
        assert payload_attributes is None
        if self.eth is not None:
            self.eth.name(forkchoice_state.head_block_hash)
        call = len(self.states)
        self.states.append(forkchoice_state)
        self.versions.append(version)
        if self.clock is not None:
            self.times.append(self.clock.now)
        return ForkchoiceUpdateResponse(
            payload_status=PayloadStatus(
                status=self.verdict(call),
                latest_valid_hash=self.latest_valid_hash,
                validation_error=None,
            ),
            payload_id=None,
        )

    def new_payload(self, *params: Any, version: int) -> PayloadStatus:
        """Fail: a head named by hash is never sent as a payload."""
        del params, version
        raise AssertionError("newPayload sent for a pre-merge head")


@dataclass
class FakeEth:
    """
    An eth API whose head is imported at `imported_at` fake seconds.

    `held` blocks are imported from the start. The canonical head is the
    last block a forkchoice update named, once it is imported, as a
    client sets it; `state_root` overrides the fixture head's root.
    """

    clock: FakeClock
    case: SyncTargetCase
    imported_at: float
    state_root: Hash | None = None
    held: set[Hash] = field(default_factory=set)
    named: Hash | None = None

    def name(self, block_hash: Hash) -> None:
        """Record the block a forkchoice update named."""
        self.named = block_hash

    def imported(self, block_hash: Hash) -> bool:
        """Return whether the client holds `block_hash` now."""
        return block_hash in self.held or (
            block_hash == self.case.chain.head.block_hash
            and self.clock.now >= self.imported_at
        )

    def get_block_by_hash(
        self, block_hash: Hash, full_txs: bool = True
    ) -> Any:
        """Return an imported block."""
        del full_txs
        if self.imported(block_hash):
            return {"hash": str(block_hash)}
        return None

    def get_block_by_number(
        self, block_number: int | str = "latest", full_txs: bool = True
    ) -> Any:
        """Return genesis for 0 and the canonical head otherwise."""
        del full_txs
        named = self.named
        if block_number == 0 or named is None or not self.imported(named):
            return {"hash": str(GENESIS_HASH), "stateRoot": "0x"}
        number = self.case.chain.number_of(named)
        assert number is not None
        block = self.case.chain.blocks[number - 1]
        root = block.state_root
        if block is self.case.chain.head and self.state_root is not None:
            root = self.state_root
        return {"hash": str(named), "stateRoot": str(root)}


def _prefix(case: SyncTargetCase) -> set[Hash]:
    """Return the hashes of every block below the head of `case`."""
    return {block.block_hash for block in case.chain.blocks[:-1]}


@dataclass
class FakePeer:
    """A peer that served every block of `chain` bar the listed ones."""

    chain: Chain
    unserved_headers: Collection[int] = ()
    unserved_bodies: Collection[int] = ()
    alive: bool = True
    disconnect_reason: int | None = None
    statistics: PeerStatistics = field(default_factory=PeerStatistics)

    def __post_init__(self) -> None:
        """Record every block as served, bar the unserved ones."""
        blocks = self.chain.blocks
        self.header_hashes_ever_served = {
            b.block_hash
            for b in blocks
            if b.number not in self.unserved_headers
        }
        self.body_hashes_ever_served = {
            b.block_hash
            for b in blocks
            if b.number not in self.unserved_bodies
        }


def _run(
    case: SyncTargetCase,
    engine: FakeEngine,
    eth: FakeEth,
    peer: FakePeer | None = None,
) -> None:
    """Run the pre-merge runner for `case` against the fakes."""
    engine.eth = eth
    test_via_wirex._run_pre_merge_target(
        case=case,
        client=cast(Any, type("Client", (), {"id": "client"})()),
        eth_rpc=cast(EthRPC, eth),
        engine_rpc=cast(EngineRPC, engine),
        mock_peer=cast(MockPeer, peer or FakePeer(case.chain)),
        timing_data=TimingData("Total"),
        genesis_verified_clients=set(),
        genesis_header=cast(FixtureHeader, _Genesis()),
        sync_timeout=SYNC_TIMEOUT,
        poll_interval=POLL_INTERVAL,
        announce_interval=ANNOUNCE_INTERVAL,
    )


class TestValidChain:
    """A valid chain passes once its head is canonical with its root."""

    def test_only_forkchoice_v1_names_the_head(self, clock: FakeClock) -> None:
        """
        No payload is sent; every update names the head by hash with the
        zero hash as safe and finalized block.
        """
        case = _case(3)
        engine = FakeEngine()
        _run(case, engine, FakeEth(clock, case, imported_at=2.5))
        assert engine.versions and set(engine.versions) == {1}
        for state in engine.states:
            assert state.head_block_hash == case.chain.head.block_hash
            assert state.safe_block_hash == Hash(0)
            assert state.finalized_block_hash == Hash(0)

    def test_the_head_is_named_again_every_interval(
        self, clock: FakeClock
    ) -> None:
        """Re-announcements keep the one-second cadence until import."""
        case = _case(2)
        engine = FakeEngine(clock=clock)
        _run(case, engine, FakeEth(clock, case, imported_at=3.5))
        assert engine.times[:4] == pytest.approx(
            [0.0, 1.0, 2.0, 3.0], abs=10 * POLL_INTERVAL
        )

    def test_a_wrong_state_root_fails(self, clock: FakeClock) -> None:
        """The head's state root must be the fixture's."""
        case = _case(2)
        eth = FakeEth(clock, case, imported_at=0.0, state_root=Hash(7))
        with pytest.raises(LoggedError, match="state root"):
            _run(case, FakeEngine(), eth)

    def test_a_rejection_fails_at_once(self, clock: FakeClock) -> None:
        """INVALID for a head the client does not hold is a verdict."""
        case = _case(2)
        engine = FakeEngine(verdict=lambda _call: PayloadStatusEnum.INVALID)
        with pytest.raises(LoggedError, match="rejected the fixture head"):
            _run(case, engine, FakeEth(clock, case, imported_at=NEVER))
        assert clock.now < ANNOUNCE_INTERVAL

    def test_a_held_head_passes_despite_invalid(
        self, clock: FakeClock
    ) -> None:
        """A client may answer INVALID for a head it already holds."""
        case = _case(2)
        engine = FakeEngine(verdict=lambda _call: PayloadStatusEnum.INVALID)
        _run(case, engine, FakeEth(clock, case, imported_at=0.0))

    def test_a_head_never_imported_fails(self, clock: FakeClock) -> None:
        """Without an import the sync timeout ends the test."""
        case = _case(2)
        with pytest.raises(LoggedError, match="never imported"):
            _run(case, FakeEngine(), FakeEth(clock, case, imported_at=NEVER))

    def test_the_head_body_must_travel(self, clock: FakeClock) -> None:
        """The head is owed over devp2p too, body and all."""
        case = _case(2)
        peer = FakePeer(case.chain, unserved_bodies=(2,))
        with pytest.raises(LoggedError, match="non-empty body"):
            _run(case, FakeEngine(), FakeEth(clock, case, 0.0), peer)


class TestInvalidChain:
    """An invalid chain passes on INVALID once its headers traveled."""

    def test_zero_latest_valid_hash_passes(self, clock: FakeClock) -> None:
        """The all-zero hash names the PoW parent of the invalid block."""
        case = _case(3, invalid_head=True)
        engine = FakeEngine(
            verdict=lambda call: (
                PayloadStatusEnum.INVALID
                if call >= 2
                else PayloadStatusEnum.SYNCING
            ),
            latest_valid_hash=Hash(0),
        )
        eth = FakeEth(clock, case, imported_at=NEVER, held=_prefix(case))
        _run(case, engine, eth)
        # Three updates name the invalid head, the last one rejected,
        # then one names its valid parent, block 2.
        assert [state.head_block_hash for state in engine.states] == [
            Hash(3),
            Hash(3),
            Hash(3),
            Hash(2),
        ]

    def test_bodies_are_not_owed(self, clock: FakeClock) -> None:
        """A header rejection fetches no body, and needs none."""
        case = _case(1, invalid_head=True)
        engine = FakeEngine(verdict=lambda _call: PayloadStatusEnum.INVALID)
        peer = FakePeer(case.chain, unserved_bodies=(1,))
        _run(case, engine, FakeEth(clock, case, NEVER), peer)
        assert len(engine.states) == 1

    def test_the_valid_parent_must_be_held(self, clock: FakeClock) -> None:
        """A client that never imports the valid parent fails."""
        case = _case(2, invalid_head=True)
        engine = FakeEngine(verdict=lambda _call: PayloadStatusEnum.INVALID)
        with pytest.raises(LoggedError, match="valid parent"):
            _run(case, engine, FakeEth(clock, case, NEVER))

    def test_the_valid_parent_body_must_travel(self, clock: FakeClock) -> None:
        """The valid parent counts as a valid chain, bodies and all."""
        case = _case(2, invalid_head=True)
        engine = FakeEngine(verdict=lambda _call: PayloadStatusEnum.INVALID)
        peer = FakePeer(case.chain, unserved_bodies=(1,))
        eth = FakeEth(clock, case, NEVER, held=_prefix(case))
        with pytest.raises(LoggedError, match="non-empty body"):
            _run(case, engine, eth, peer)

    def test_the_head_header_must_travel(self, clock: FakeClock) -> None:
        """A verdict on a head never fetched is no wire evidence."""
        case = _case(2, invalid_head=True)
        engine = FakeEngine(verdict=lambda _call: PayloadStatusEnum.INVALID)
        peer = FakePeer(case.chain, unserved_headers=(2,))
        with pytest.raises(LoggedError, match="header"):
            _run(case, engine, FakeEth(clock, case, NEVER), peer)

    def test_acceptance_fails(self, clock: FakeClock) -> None:
        """VALID for an invalid head fails at once."""
        case = _case(2, invalid_head=True)
        engine = FakeEngine(verdict=lambda _call: PayloadStatusEnum.VALID)
        with pytest.raises(LoggedError, match="accepted the invalid"):
            _run(case, engine, FakeEth(clock, case, NEVER))

    def test_no_verdict_fails(self, clock: FakeClock) -> None:
        """SYNCING until the timeout fails."""
        case = _case(2, invalid_head=True)
        with pytest.raises(LoggedError, match="never rejected"):
            _run(case, FakeEngine(), FakeEth(clock, case, NEVER))

    def test_a_hash_off_the_chain_fails(self, clock: FakeClock) -> None:
        """A latest valid hash naming no block of the path blames wrong."""
        case = _case(2, invalid_head=True)
        engine = FakeEngine(
            verdict=lambda _call: PayloadStatusEnum.INVALID,
            latest_valid_hash=Hash(0xDEAD),
        )
        with pytest.raises(LoggedError, match="mismatch"):
            _run(case, engine, FakeEth(clock, case, NEVER))

    def test_the_parent_hash_passes(self, clock: FakeClock) -> None:
        """Naming the invalid block's parent itself is a match too."""
        case = _case(3, invalid_head=True)
        engine = FakeEngine(
            verdict=lambda _call: PayloadStatusEnum.INVALID,
            latest_valid_hash=Hash(2),
        )
        _run(case, engine, FakeEth(clock, case, NEVER, held=_prefix(case)))
