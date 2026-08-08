"""
Test the timestamp-monotonicity guard applied by ``--prepend-empty-block``.

Prepending an empty block at genesis + 1 can push a pinned timestamp
below its parent's, which builds a non-monotonic - consensus-invalid -
chain that no client accepts. The guard refuses such a fill loudly.

A block declaring an exception is rolled back and never becomes the
parent of its successor, so it must neither be checked against the
prepended block nor advance the walk.
"""

import textwrap
from typing import Any

rolled_back_block_module = textwrap.dedent(
    """\
    import pytest

    from execution_testing import Block, Transaction, TransactionException


    @pytest.mark.exception_test
    def test_rolled_back_block_does_not_advance(
        blockchain_test, pre
    ) -> None:
        # The rejected block never consumes its sender's nonce, so the
        # accepted block uses a sender of its own.
        rejected_sender = pre.fund_eoa()
        accepted_sender = pre.fund_eoa()
        blockchain_test(
            pre=pre,
            post={},
            blocks=[
                Block(
                    timestamp=1000,
                    txs=[
                        Transaction(
                            to=0,
                            gas_limit=20_999,
                            sender=rejected_sender,
                            error=(
                                TransactionException.INTRINSIC_GAS_TOO_LOW
                            ),
                        )
                    ],
                    exception=TransactionException.INTRINSIC_GAS_TOO_LOW,
                ),
                Block(
                    timestamp=1000,
                    txs=[
                        Transaction(
                            to=0,
                            gas_limit=21_000,
                            sender=accepted_sender,
                        )
                    ],
                ),
            ],
        )
    """
)

colliding_timestamps_module = textwrap.dedent(
    """\
    import pytest

    from execution_testing import Block, Transaction


    def test_colliding_timestamps(blockchain_test, pre) -> None:
        sender = pre.fund_eoa()
        blockchain_test(
            pre=pre,
            post={},
            blocks=[
                Block(
                    timestamp=1000,
                    txs=[
                        Transaction(
                            to=0, gas_limit=21_000, sender=sender
                        )
                    ],
                ),
                Block(
                    timestamp=1000,
                    txs=[
                        Transaction(
                            to=0, gas_limit=21_000, sender=sender
                        )
                    ],
                ),
            ],
        )
    """
)


def make_test_module(pytester: Any, source: str, name: str) -> Any:
    """Write a test module into a pytester tests tree."""
    tests_dir = pytester.mkdir("tests")
    cancun_tests_dir = tests_dir / "cancun"
    cancun_tests_dir.mkdir()
    module_dir = cancun_tests_dir / "prepend_timestamps_module"
    module_dir.mkdir()
    test_module = module_dir / name
    test_module.write_text(source)
    pytester.copy_example(
        name="src/execution_testing/cli/pytest_commands/pytest_ini_files/pytest-fill.ini"
    )
    return test_module


def run_fill(pytester: Any, test_module: Any) -> Any:
    """Fill the given module with the prepend option enabled."""
    return pytester.runpytest_subprocess(
        "-c",
        "pytest-fill.ini",
        "--fork",
        "Cancun",
        "-m",
        "blockchain_test",
        "--prepend-empty-block",
        "--no-html",
        "--output=stdout",
        str(test_module.relative_to(pytester.path)),
    )


def test_rolled_back_block_does_not_advance_the_walk(
    pytester: Any,
) -> None:
    """A repeated timestamp after a rejected block must still fill."""
    test_module = make_test_module(
        pytester,
        rolled_back_block_module,
        "test_rolled_back_block.py",
    )
    result = run_fill(pytester, test_module)
    outcomes = result.parseoutcomes()
    assert outcomes.get("passed", 0) > 0
    assert outcomes.get("failed", 0) == 0


def test_colliding_timestamps_fail_the_fill(
    pytester: Any, capsys: Any
) -> None:
    """Two valid blocks pinning one timestamp must fail loudly."""
    test_module = make_test_module(
        pytester,
        colliding_timestamps_module,
        "test_colliding_timestamps.py",
    )
    result = run_fill(pytester, test_module)
    capsys.readouterr()  # suppress inner failure bleed
    assert result.ret != 0
    result.stdout.fnmatch_lines(["*does not clear its parent*"])
