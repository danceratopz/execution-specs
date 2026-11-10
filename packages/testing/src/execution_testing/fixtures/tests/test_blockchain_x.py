"""Test the `blockchain_test_x` fixture format."""

from copy import deepcopy
from typing import Any, Dict

import pytest

from execution_testing.base_types import Address, Bytes, Hash
from execution_testing.forks import (
    BerlinToLondonAt5,
    Frontier,
    GrayGlacier,
    Paris,
    ParisToShanghaiAtTime15k,
    get_forks,
    get_transition_forks,
)
from execution_testing.specs import BlockchainTest, StateTest
from execution_testing.test_types import (
    Account,
    Alloc,
    AllocGroupHash,
    Environment,
)

from ..base import BaseFixture, FixtureFillingPhase
from ..blockchain import (
    BlockchainEngineXFixture,
    BlockchainFixture,
    BlockchainXFixture,
    FixtureBlockBase,
    FixtureConfig,
    FixtureHeader,
)


def make_fixture() -> BlockchainXFixture:
    """Return a minimal fixture with one empty block on a Frontier genesis."""
    genesis = FixtureHeader.genesis(Frontier, Environment(), Hash(1))
    header = FixtureHeader.genesis(Frontier, Environment(), Hash(2))
    header = header.model_copy(
        update={"number": 1, "parent_hash": genesis.block_hash}
    )
    block = FixtureBlockBase(header=header).with_rlp(txs=[])
    fixture = BlockchainXFixture(
        fork=Frontier,
        genesis=genesis,
        genesis_rlp=Bytes(b"\x01"),
        blocks=[block],
        last_block_hash=block.header.block_hash,
        post_state_hash=Hash(2),
        config=FixtureConfig(fork=Frontier),
        pre_hash=AllocGroupHash("0x0123456789abcdef"),
        post_state_diff=Alloc({Address(0x1000): Account(balance=1)}),
    )
    # Parse once, as a consumer reading a filled file does: a parsed
    # block carries its computed `blocknumber`, a freshly built one not.
    return BlockchainXFixture.model_validate(deepcopy(fixture.json_dict))


def test_format_is_registered() -> None:
    """The format registers under its name and writes its own directory."""
    assert BaseFixture.formats["blockchain_test_x"] is BlockchainXFixture
    assert BlockchainXFixture.output_base_dir_name() == "blockchain_tests_x"


def test_fills_in_the_pre_allocation_phases() -> None:
    """
    The format fills only in the two pre-allocation phases, exactly like
    Engine X, so phase 1 groups its tests and a plain fill skips it.
    """
    assert BlockchainXFixture.format_phases == {
        FixtureFillingPhase.PRE_ALLOC_GENERATION,
        FixtureFillingPhase.FILL_AFTER_PRE_ALLOC_GENERATION,
    }
    assert (
        BlockchainXFixture.format_phases
        == BlockchainEngineXFixture.format_phases
    )
    assert FixtureFillingPhase.FILL not in BlockchainXFixture.format_phases


def test_supports_the_forks_before_paris() -> None:
    """The format fills the forks before Paris, Engine X those after."""
    assert BlockchainXFixture.supports_fork(Frontier)
    assert BlockchainXFixture.supports_fork(BerlinToLondonAt5)
    # Not an ancestor of Paris, but still before the merge.
    assert BlockchainXFixture.supports_fork(GrayGlacier)
    assert not BlockchainXFixture.supports_fork(Paris)
    assert not BlockchainXFixture.supports_fork(ParisToShanghaiAtTime15k)


@pytest.mark.parametrize(
    "fork",
    [*get_forks(), *sorted(get_transition_forks(), key=str)],
    ids=str,
)
def test_every_fork_has_one_grouped_format(fork: Any) -> None:
    """Exactly one of the two grouped formats fills each fork."""
    assert BlockchainXFixture.supports_fork(
        fork
    ) != BlockchainEngineXFixture.supports_fork(fork)


def test_round_trip() -> None:
    """The fixture serializes to the documented keys and parses back."""
    fixture = make_fixture()
    json_dict = fixture.json_dict_with_info()
    assert set(json_dict) == {
        "_info",
        "network",
        "genesisBlockHeader",
        "genesisRLP",
        "blocks",
        "lastblockhash",
        "postStateHash",
        "config",
        "sealEngine",
        "preHash",
        "postStateDiff",
    }
    assert "pre" not in json_dict
    assert "postState" not in json_dict
    # Parsing strips computed fields from its input in place.
    parsed = BlockchainXFixture.model_validate(deepcopy(json_dict))
    assert parsed.json_dict == fixture.json_dict


def test_parses_by_format_name() -> None:
    """A fixture file entry parses into the format named in its info."""
    fixture = make_fixture()
    fixture.fill_info(
        "t8n",
        "test",
        fixture_source_url="",
        ref_spec=None,
        _info_metadata={},
    )
    json_dict: Dict[str, Any] = fixture.json_dict_with_info()
    parsed = BaseFixture.formats_type_adapter.validate_python(json_dict)
    assert isinstance(parsed, BlockchainXFixture)


def test_requires_the_group_and_the_post_state_diff() -> None:
    """A fixture without its group hash or its state diff is invalid."""
    json_dict = make_fixture().json_dict
    for key in ("preHash", "postStateDiff"):
        incomplete = {k: v for k, v in json_dict.items() if k != key}
        with pytest.raises(ValueError):
            BlockchainXFixture.model_validate(incomplete)


class TestTransitionToolCache:
    """
    The format runs against the group's genesis, so it must never read
    transition tool outputs another format cached for the same test.

    The cache is keyed by the test's node id without the format plus the
    format's cache key, and serves outputs by call index, not by input:
    a `blockchain_test` key would hand this format outputs computed on
    the test's own genesis.
    """

    def test_opts_out_of_the_cache(self) -> None:
        """The format has no cache key."""
        assert BlockchainXFixture.transition_tool_cache_key == ""
        assert (
            BlockchainXFixture.transition_tool_cache_key
            != BlockchainFixture.transition_tool_cache_key
        )

    def test_marks_carry_no_cache_key(self) -> None:
        """No `transition_tool_cache_key` marker reaches the test item."""
        names = [mark.name for mark in BlockchainXFixture.marks()]
        assert names == ["blockchain_test_x"]

    def test_state_test_label_opts_out_too(self) -> None:
        """The label a state test derives keeps the empty key."""
        labels = [
            fixture_format
            for fixture_format in StateTest.supported_fixture_formats
            if fixture_format == BlockchainXFixture
        ]
        assert [label.format_id() for label in labels] == [
            "blockchain_test_x_from_state_test"
        ]
        for label in labels:
            assert label.transition_tool_cache_key == ""
            names = [mark.name for mark in label.marks()]
            assert "transition_tool_cache_key" not in names


class TestSpecTypes:
    """Which spec types fill the format, and which markers veto it."""

    def test_blockchain_test_fills_the_format(self) -> None:
        """Blockchain tests fill it, after the primary `blockchain_test`."""
        formats = BlockchainTest.supported_fixture_formats
        assert BlockchainXFixture in formats
        assert formats[0] == BlockchainFixture

    @pytest.mark.parametrize(
        "marker,discarded",
        [
            ("blockchain_test_only", False),
            ("blockchain_test_engine_only", True),
        ],
    )
    def test_markers(self, marker: str, discarded: bool) -> None:
        """It is an RLP format: kept with `blockchain_test_only` only."""
        mark = pytest.Mark(marker, (), {})
        assert (
            BlockchainTest.discard_fixture_format_by_marks(
                BlockchainXFixture, [mark]
            )
            is discarded
        )
