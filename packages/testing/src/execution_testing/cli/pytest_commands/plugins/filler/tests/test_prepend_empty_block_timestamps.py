"""
Test the timestamp-monotonicity guard applied by the prepended empty
block.

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
    """
    Fill the given module's engine_x fixtures and return the phase-2
    result.

    Only engine_x fixtures carry the prepended block, and they fill in
    the second of the two fill phases (the guard runs when the chain
    is built, which phase 1 never does), so phase 1 is expected to
    succeed either way and the interesting result is phase 2's.
    """
    output = pytester.path / "fixtures"
    common = (
        "-c",
        "pytest-fill.ini",
        "--fork",
        "Cancun",
        "--generate-all-formats",
        "--prepend-empty-block",
        "--skip-index",
        "--no-html",
        f"--output={output}",
        str(test_module.relative_to(pytester.path)),
    )
    result = pytester.runpytest_subprocess(
        "--generate-pre-alloc-groups", *common
    )
    assert result.ret == 0, "fill phase 1 was expected to succeed"
    return pytester.runpytest_subprocess("--use-pre-alloc-groups", *common)


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
