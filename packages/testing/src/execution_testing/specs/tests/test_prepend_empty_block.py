"""
Tests for the ``prepend_empty_block`` fill option.

When the option is set the chain gains one empty block between genesis
and the test's first block, so that every chain is at least two blocks
long and a sync-based consumer can always trigger a devp2p sync.
"""

from hashlib import sha256
from typing import List

from execution_testing.forks import Cancun
from execution_testing.specs.blockchain import Block, BlockchainTest
from execution_testing.test_types import Alloc

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
