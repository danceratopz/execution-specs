"""
Tests for the blocks a mock peer serves.

Blocks rebuilt from Engine API payloads self-check each header's hash
but not its body, so these check every rebuilt body against the roots
its header commits to. Blocks served from fixture RLP are checked
against the decoded fixture blocks.
"""

import dataclasses
import functools
import json
from pathlib import Path
from typing import Any, List, Sequence, Tuple, cast

import ethereum_rlp as eth_rlp
import pytest
from ethereum_types.numeric import Uint
from trie import HexaryTrie

from execution_testing.base_types import Address, Bytes
from execution_testing.fixtures.blockchain import (
    BlockchainEngineFixture,
    BlockchainFixture,
    FixtureBlock,
    FixtureEngineNewPayload,
    FixtureHeader,
)
from execution_testing.test_types.block_types import Withdrawal

from ..chain import (
    Block,
    Chain,
    ChainReconstructionError,
    RlpBlock,
    UndecodableBlockError,
    chain_from_payloads,
    linked_chain,
)

FIXTURES = Path(__file__).parents[2] / "specs" / "tests" / "fixtures"

ENGINE_FIXTURES = [
    "blockchain_shanghai_valid_filled_engine.json",
    "chainid_cancun_blockchain_test_engine_tx_type_0.json",
]


@functools.cache
def _fixture(name: str = ENGINE_FIXTURES[0]) -> BlockchainEngineFixture:
    """Load the single engine fixture in the file `name`."""
    (fixture,) = json.loads((FIXTURES / name).read_text()).values()
    return BlockchainEngineFixture.model_validate(fixture)


def _trie_root(items: Sequence[bytes]) -> bytes:
    """Return the root of the trie keyed by each item's index."""
    trie = HexaryTrie(db={})
    for index, item in enumerate(items):
        trie.set(eth_rlp.encode(Uint(index)), item)
    return trie.root_hash


def _decoded_body(body_rlp: bytes) -> List[Any]:
    """Decode a body into its transactions, ommers and withdrawals."""
    return cast(List[Any], eth_rlp.decode(body_rlp))


def _transaction_bytes(item: Any) -> bytes:
    """
    Return a decoded body transaction as the bytes its trie holds.

    A legacy transaction decodes as a list, a typed one as the byte
    string of its type prefix and payload.
    """
    return item if isinstance(item, bytes) else eth_rlp.encode(item)


def _shanghai_head() -> Block:
    """Return the rebuilt head block of the Shanghai engine fixture."""
    fixture = _fixture()
    return cast(
        Block, chain_from_payloads(fixture.genesis, fixture.payloads).head
    )


def _tampered(payload: FixtureEngineNewPayload) -> FixtureEngineNewPayload:
    """Return `payload` with its extra data changed, hash unchanged."""
    execution_payload, *rest = payload.params
    changed = execution_payload.model_copy(
        update={"extra_data": Bytes(b"tampered")}
    )
    return payload.model_copy(update={"params": (changed, *rest)})


class TestChainFromPayloads:
    """A fixture's payloads rebuild into the chain they deliver."""

    @pytest.mark.parametrize("name", ENGINE_FIXTURES)
    def test_chain_from_payloads_round_trips(self, name: str) -> None:
        """Every block hashes as declared; every body matches its roots."""
        fixture = _fixture(name)
        chain = chain_from_payloads(fixture.genesis, fixture.payloads)

        assert len(chain.blocks) == len(fixture.payloads)
        assert chain.head.block_hash == bytes(fixture.last_block_hash)
        for served, payload in zip(
            chain.blocks, fixture.payloads, strict=True
        ):
            block = cast(Block, served)
            execution_payload = payload.params[0]
            assert block.block_hash == bytes(execution_payload.block_hash)
            assert chain.number_of(block.block_hash) == block.number

            body_rlp = chain.body_rlp_by_hash(block.block_hash)
            assert body_rlp == block.body_rlp()
            transactions, ommers, withdrawals = _decoded_body(body_rlp)
            raw = [_transaction_bytes(item) for item in transactions]
            assert raw == [bytes(t) for t in execution_payload.transactions]
            assert _trie_root(raw) == bytes(block.header.transactions_trie)
            assert ommers == []
            assert block.header.withdrawals_root is not None
            assert _trie_root(
                [eth_rlp.encode(withdrawal) for withdrawal in withdrawals]
            ) == bytes(block.header.withdrawals_root)

    def test_a_tampered_payload_is_refused(self) -> None:
        """A payload whose fields no longer hash to its block is refused."""
        fixture = _fixture()
        payloads = list(fixture.payloads)
        payloads[1] = _tampered(payloads[1])
        with pytest.raises(ChainReconstructionError, match="hashes to"):
            chain_from_payloads(fixture.genesis, payloads)

    @pytest.mark.parametrize(
        "order",
        [
            pytest.param((1, 0, 2, 3), id="reordered"),
            pytest.param((0, 2, 3), id="gap"),
        ],
    )
    def test_a_broken_chain_is_refused(self, order: Tuple[int, ...]) -> None:
        """Blocks that do not each extend their predecessor are refused."""
        fixture = _fixture()
        payloads = [fixture.payloads[index] for index in order]
        with pytest.raises(
            ChainReconstructionError, match="does not extend its predecessor"
        ):
            chain_from_payloads(fixture.genesis, payloads)


class TestBodyShape:
    """A body carries exactly the lists its header commits to."""

    def test_withdrawals_encode_as_their_root_commits(self) -> None:
        """The served withdrawals hash to `Withdrawal.list_root`."""
        block = _shanghai_head()
        withdrawals = [
            Withdrawal(
                index=index,
                validator_index=index + 7,
                address=Address(0x100 + index),
                amount=10**9 + index,
            )
            for index in range(3)
        ]
        body = dataclasses.replace(block, withdrawals=withdrawals).body_rlp()
        _, _, served = _decoded_body(body)
        assert _trie_root(
            [eth_rlp.encode(withdrawal) for withdrawal in served]
        ) == bytes(Withdrawal.list_root(withdrawals))

    def test_a_block_without_withdrawals_serves_two_lists(self) -> None:
        """A pre-Shanghai body has no withdrawals list at all."""
        block = _shanghai_head()
        body = dataclasses.replace(block, withdrawals=None).body_rlp()
        assert len(_decoded_body(body)) == 2

    @pytest.mark.parametrize(
        "with_withdrawals,expected",
        [
            pytest.param(True, b"\xc3\xc0\xc0\xc0", id="shanghai"),
            pytest.param(False, b"\xc2\xc0\xc0", id="paris"),
        ],
    )
    def test_genesis_body_follows_its_header(
        self, with_withdrawals: bool, expected: bytes
    ) -> None:
        """Genesis has a withdrawals list exactly when it has a root."""
        shanghai = _fixture().genesis
        assert shanghai.withdrawals_root is not None
        genesis = (
            shanghai
            if with_withdrawals
            else FixtureHeader(
                **shanghai.model_dump(exclude={"withdrawals_root"})
            )
        )
        chain = Chain(genesis, [])
        assert chain.body_rlp_by_hash(genesis.block_hash) == expected


RLP_FIXTURES = {
    "valid": "blockchain_london_valid_filled.json",
    "invalid": "blockchain_london_invalid_filled.json",
}


@functools.cache
def _rlp_fixture(name: str) -> BlockchainFixture:
    """Load the single blockchain_test fixture in the file `name`."""
    (fixture,) = json.loads((FIXTURES / name).read_text()).values()
    return BlockchainFixture.model_validate(fixture)


def _header_list(header: FixtureHeader) -> List[Any]:
    """Return `header` decoded into its RLP fields."""
    return cast(List[Any], eth_rlp.decode(bytes(header.rlp)))


class TestRlpBlock:
    """A fixture block's RLP splits into the header and body it serves."""

    def test_a_valid_chain_serves_its_fixture_headers(self) -> None:
        """Each block hashes as declared and links to its parent."""
        fixture = _rlp_fixture(RLP_FIXTURES["valid"])
        blocks = []
        for entry in fixture.blocks:
            assert isinstance(entry, FixtureBlock)
            block = RlpBlock.from_rlp(bytes(entry.rlp))
            assert block.block_hash == entry.header.block_hash
            assert block.header_rlp() == bytes(entry.header.rlp)
            assert block.number == int(entry.header.number)
            assert block.timestamp == int(entry.header.timestamp)
            assert block.state_root == entry.header.state_root
            assert block.difficulty == int(entry.header.difficulty)
            assert block.owes_body == bool(entry.txs)
            blocks.append(block)
        chain = linked_chain(fixture.genesis, blocks)
        assert chain.head.block_hash == fixture.last_block_hash
        assert chain.total_difficulty == int(fixture.genesis.difficulty) + sum(
            int(cast(FixtureBlock, entry).header.difficulty)
            for entry in fixture.blocks
        )

    def test_the_body_is_the_rest_of_the_block(self) -> None:
        """The served body is the block's lists after the header."""
        fixture = _rlp_fixture(RLP_FIXTURES["valid"])
        entry = fixture.blocks[0]
        _, *body = cast(List[Any], eth_rlp.decode(bytes(entry.rlp)))
        block = RlpBlock.from_rlp(bytes(entry.rlp))
        assert block.body_rlp() == eth_rlp.encode(body)
        assert Chain(fixture.genesis, [block]).body_rlp_by_hash(
            block.block_hash
        ) == eth_rlp.encode(body)

    def test_an_invalid_block_is_served_as_declared(self) -> None:
        """An expected-invalid block still splits; its parent links."""
        fixture = _rlp_fixture(RLP_FIXTURES["invalid"])
        valid = RlpBlock.from_rlp(bytes(fixture.blocks[1].rlp))
        invalid = RlpBlock.from_rlp(bytes(fixture.blocks[2].rlp))
        assert not isinstance(fixture.blocks[2], FixtureBlock)
        assert invalid.parent_hash == valid.block_hash
        assert invalid.number == valid.number + 1

    @pytest.mark.parametrize(
        "uncles, owes",
        [([], False), (["uncle"], True)],
        ids=["empty", "uncle-only"],
    )
    def test_an_uncle_alone_makes_the_body_owed(
        self, uncles: List[str], owes: bool
    ) -> None:
        """A body without transactions but with an uncle is fetched."""
        genesis = _header_list(_rlp_fixture(RLP_FIXTURES["valid"]).genesis)
        body_uncles = [genesis for _ in uncles]
        block = RlpBlock.from_rlp(eth_rlp.encode([genesis, [], body_uncles]))
        assert block.owes_body is owes
        assert block.body_rlp() == eth_rlp.encode([[], body_uncles])

    @pytest.mark.parametrize(
        "block_rlp",
        [
            pytest.param(b"\xf8", id="truncated"),
            pytest.param(eth_rlp.encode(b"block"), id="not-a-list"),
            pytest.param(
                eth_rlp.encode([[b""] * 14, [], []]), id="short-header"
            ),
            pytest.param(eth_rlp.encode([[b""] * 15, []]), id="no-uncle-list"),
            pytest.param(
                eth_rlp.encode([[b""] * 15, b"", []]), id="body-not-a-list"
            ),
            pytest.param(
                eth_rlp.encode([[b"\x00" * 31] + [b""] * 14, [], []]),
                id="short-parent-hash",
            ),
        ],
    )
    def test_an_unservable_block_is_refused(self, block_rlp: bytes) -> None:
        """RLP that is not a header and body lists cannot be served."""
        with pytest.raises(UndecodableBlockError):
            RlpBlock.from_rlp(block_rlp)

    def test_a_gap_is_refused(self) -> None:
        """A block that does not name its predecessor breaks the chain."""
        fixture = _rlp_fixture(RLP_FIXTURES["valid"])
        blocks = [RlpBlock.from_rlp(bytes(b.rlp)) for b in fixture.blocks]
        with pytest.raises(
            ChainReconstructionError, match="block 3 does not extend"
        ):
            linked_chain(fixture.genesis, [blocks[0], blocks[2]])
