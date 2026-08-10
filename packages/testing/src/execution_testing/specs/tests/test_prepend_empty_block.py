"""
Tests for the ``prepend_empty_block`` fill option.

Two things happen when the option is set: the chain gains one empty
block between genesis and the test's first block, and genesis is wound
one fee progression step up so that block consumes exactly the step it
introduces. The prepended block decays the base fee by one EIP-1559
step and the excess blob gas by one target, so compensation lands it
precisely on the fee values the test author gave for genesis.
"""

from hashlib import sha256
from typing import List

import pytest

from execution_testing.base_types import HexNumber
from execution_testing.forks import Cancun, Fork, London, Osaka, Shanghai
from execution_testing.specs.blockchain import (
    Block,
    BlockchainTest,
    empty_block_base_fee_preimage,
    empty_block_excess_blob_gas_preimage,
)
from execution_testing.specs.state import StateTest
from execution_testing.test_types import (
    Alloc,
    Environment,
    Transaction,
)

GAS_LIMIT = 100_000_000
CANCUN_TARGET_BLOB_GAS = (
    Cancun.target_blobs_per_block() * Cancun.blob_gas_per_blob()
)
SALT = "tests/cancun/test_x.py::test_y[fork_Cancun-blockchain_test]"


def make_prepend_test(
    *, blocks: List[Block], salt: str = SALT, prepend: bool = True
) -> BlockchainTest:
    """Create a Cancun blockchain test over the given blocks."""
    return BlockchainTest(
        fork=Cancun,
        pre=Alloc(),
        post=Alloc(),
        blocks=blocks,
        prepend_empty_block=prepend,
        prepend_empty_block_salt=salt,
    )


def test_blocks_to_build_prepends_one_empty_block() -> None:
    """
    The chain gains one empty block at genesis + 1 carrying a digest of
    the test's salt in its ``extra_data``.
    """
    test = make_prepend_test(blocks=[Block(timestamp=1_000)])
    blocks = test.blocks_to_build()
    assert len(blocks) == 2
    prepended = blocks[0]
    assert prepended.timestamp == 1
    assert prepended.txs == []
    assert prepended.extra_data == sha256(SALT.encode()).digest()[:16]
    assert blocks[1] is test.blocks[0], "the test's own block passes through"


def test_prepended_block_differs_per_test() -> None:
    """
    Tests of a pre-allocation group must not share the prepended block:
    a client that already knows it never starts a sync.
    """
    first = make_prepend_test(blocks=[], salt="a").blocks_to_build()
    second = make_prepend_test(blocks=[], salt="b").blocks_to_build()
    assert first[0].extra_data != second[0].extra_data


def test_blocks_to_build_shifts_pinned_block_numbers() -> None:
    """A block pinning an absolute number shifts up to stay contiguous."""
    test = make_prepend_test(
        blocks=[Block(number=1, timestamp=1_000), Block(timestamp=2_000)]
    )
    numbers = [block.number for block in test.blocks_to_build()]
    assert numbers == [None, 2, None]
    assert test.blocks[0].number == 1, "the test's own block is untouched"


def test_blocks_to_build_without_the_option_is_a_no_op() -> None:
    """
    Without the option the test's own blocks are built as given, and no
    timestamp is checked against a block that is never prepended.
    """
    test = make_prepend_test(blocks=[Block(timestamp=1)], prepend=False)
    assert test.blocks_to_build() is test.blocks


@pytest.mark.parametrize(
    "base_fee_per_gas",
    [0, 1, 6, 7, 8, 9, 10, 100, 1_000, 875_000_000, 1_000_000_000],
)
@pytest.mark.parametrize("fork", [London, Cancun])
def test_base_fee_preimage_round_trip(
    fork: Fork, base_fee_per_gas: int
) -> None:
    """An empty block must decay the preimage to the intended value."""
    preimage = empty_block_base_fee_preimage(
        fork=fork,
        base_fee_per_gas=base_fee_per_gas,
        gas_limit=GAS_LIMIT,
    )
    derived = fork.base_fee_per_gas_calculator()(
        parent_base_fee_per_gas=preimage,
        parent_gas_used=0,
        parent_gas_limit=GAS_LIMIT,
    )
    assert derived == base_fee_per_gas


@pytest.mark.parametrize(
    "excess_blob_gas",
    [
        0,
        0x20000,
        0x60000,
        0x80000,
        0xE0000,
        0x12345,  # not a multiple of the blob gas quantum
    ],
)
def test_excess_blob_gas_preimage_round_trip(excess_blob_gas: int) -> None:
    """An empty block must decay the preimage to the intended value."""
    preimage = empty_block_excess_blob_gas_preimage(
        fork=Cancun,
        excess_blob_gas=excess_blob_gas,
        parent_base_fee_per_gas=7,
    )
    derived = Cancun.excess_blob_gas_calculator()(
        parent_excess_blob_gas=preimage,
        parent_blob_gas_used=0,
        parent_base_fee_per_gas=7,
    )
    assert derived == excess_blob_gas


@pytest.mark.parametrize("excess_blobs", [1, 2, 3, 4, 5])
def test_excess_blob_gas_with_no_preimage_is_refused(
    excess_blobs: int,
) -> None:
    """
    A value the reserve price makes unreachable must be refused.

    Above the reserve price an empty block leaves the excess where it
    is, so a genesis winding up to a small nonzero excess does not
    exist. This is the class the ``no_empty_block_fee_preimage`` marker
    records: refusing loudly here is what keeps a silently shifted fee
    environment out of the fixtures.
    """
    with pytest.raises(ValueError, match="no parent excess blob gas"):
        empty_block_excess_blob_gas_preimage(
            fork=Osaka,
            excess_blob_gas=excess_blobs * Osaka.blob_gas_per_blob(),
            parent_base_fee_per_gas=17,
        )


def make_blockchain_test(*, prepend_empty_block: bool) -> BlockchainTest:
    """Create a minimal Cancun blockchain test pinning genesis fees."""
    return BlockchainTest(
        fork=Cancun,
        pre=Alloc(),
        post=Alloc(),
        blocks=[],
        genesis_environment=Environment(
            base_fee_per_gas=HexNumber(10),
            excess_blob_gas=HexNumber(0x80000),
        ),
        prepend_empty_block=prepend_empty_block,
        prepend_empty_block_salt="test",
    )


def test_blockchain_test_genesis_not_compensated_by_default() -> None:
    """Without the option the author's genesis values pass through."""
    env = make_blockchain_test(
        prepend_empty_block=False
    ).get_genesis_environment()
    assert env.base_fee_per_gas == 10
    assert env.excess_blob_gas == 0x80000


def test_blockchain_test_genesis_compensation() -> None:
    """
    One empty-block step from compensated genesis lands on the
    author's genesis values.
    """
    env = make_blockchain_test(
        prepend_empty_block=True
    ).get_genesis_environment()
    assert env.base_fee_per_gas is not None
    assert env.excess_blob_gas is not None
    derived_base_fee = Cancun.base_fee_per_gas_calculator()(
        parent_base_fee_per_gas=int(env.base_fee_per_gas),
        parent_gas_used=0,
        parent_gas_limit=int(env.gas_limit),
    )
    assert derived_base_fee == 10
    derived_excess = Cancun.excess_blob_gas_calculator()(
        parent_excess_blob_gas=int(env.excess_blob_gas),
        parent_blob_gas_used=0,
        parent_base_fee_per_gas=int(env.base_fee_per_gas),
    )
    assert derived_excess == 0x80000


def test_blockchain_test_pre_blob_genesis_compensation() -> None:
    """A pre-Cancun chain compensates the base fee only."""
    test = BlockchainTest(
        fork=Shanghai,
        pre=Alloc(),
        post=Alloc(),
        blocks=[],
        genesis_environment=Environment(base_fee_per_gas=HexNumber(1000)),
        prepend_empty_block=True,
        prepend_empty_block_salt="test",
    )
    env = test.get_genesis_environment()
    assert env.base_fee_per_gas is not None
    assert env.excess_blob_gas is None
    derived_base_fee = Shanghai.base_fee_per_gas_calculator()(
        parent_base_fee_per_gas=int(env.base_fee_per_gas),
        parent_gas_used=0,
        parent_gas_limit=int(env.gas_limit),
    )
    assert derived_base_fee == 1000


def make_state_test(*, prepend_empty_block: bool) -> StateTest:
    """Create a minimal Cancun state test pinning block fee values."""
    return StateTest(
        fork=Cancun,
        pre=Alloc(),
        post=Alloc(),
        tx=Transaction(sender=HexNumber(0), to=HexNumber(0), nonce=0),
        env=Environment(
            number=1,
            timestamp=1_000,
            base_fee_per_gas=HexNumber(10),
            excess_blob_gas=HexNumber(0xE0000),
        ),
        prepend_empty_block=prepend_empty_block,
        prepend_empty_block_salt="test",
    )


def test_state_test_composition() -> None:
    """
    Two empty-block steps from a converted state test's compensated
    genesis land on the pinned block environment.

    The state-test conversion winds genesis one step up from the
    pinned block environment; the prepend compensation adds the one
    further step the prepended block consumes.
    """
    blockchain_test = make_state_test(
        prepend_empty_block=True
    ).generate_blockchain_test()
    env = blockchain_test.get_genesis_environment()
    assert env.base_fee_per_gas is not None
    assert env.excess_blob_gas is not None

    base_fee = int(env.base_fee_per_gas)
    excess = int(env.excess_blob_gas)
    base_fee_calculator = Cancun.base_fee_per_gas_calculator()
    excess_calculator = Cancun.excess_blob_gas_calculator()
    for _ in range(2):
        new_excess = excess_calculator(
            parent_excess_blob_gas=excess,
            parent_blob_gas_used=0,
            parent_base_fee_per_gas=base_fee,
        )
        base_fee = base_fee_calculator(
            parent_base_fee_per_gas=base_fee,
            parent_gas_used=0,
            parent_gas_limit=int(env.gas_limit),
        )
        excess = new_excess
    assert base_fee == 10
    assert excess == 0xE0000


def test_state_test_conversion_unchanged_without_prepend() -> None:
    """Without the option the conversion winds exactly one step up."""
    blockchain_test = make_state_test(
        prepend_empty_block=False
    ).generate_blockchain_test()
    env = blockchain_test.get_genesis_environment()
    assert env.base_fee_per_gas == 10 * 8 // 7
    assert env.excess_blob_gas == 0xE0000 + CANCUN_TARGET_BLOB_GAS
