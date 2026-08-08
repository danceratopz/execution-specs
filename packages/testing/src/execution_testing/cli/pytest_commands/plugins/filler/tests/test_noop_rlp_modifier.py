"""
Test that filling fails loudly when an expected-invalid block's
``rlp_modifier`` does not actually change the header.

A modifier that pins a header field to the value the header already
holds produces a block that is valid while the fixture claims it is
invalid. This can happen silently when the chain context shifts under
a test, e.g. when a fee progression is moved by the prepended empty
block, so the fill must refuse instead of emitting the fixture.

The refusal only applies when every expected exception is a block
exception: a block carrying an invalid transaction is invalid
regardless of its header, and the state test conversion routinely
pins header fields to values that legitimately match the computed
ones.
"""

import textwrap
from typing import Any

noop_rlp_modifier_test_module = textwrap.dedent(
    """\
    from execution_testing import Block
    from execution_testing.exceptions.exceptions import BlockException
    from execution_testing.specs.blockchain import Header


    def test_noop_rlp_modifier(blockchain_test, pre) -> None:
        blockchain_test(
            pre=pre,
            post={},
            blocks=[
                Block(
                    timestamp=12,
                    rlp_modifier=Header(timestamp=12),
                    exception=BlockException.INVALID_BLOCK_HASH,
                )
            ],
        )
    """
)


noop_modifier_tx_exception_test_module = textwrap.dedent(
    """\
    import pytest

    from execution_testing import Block, Transaction
    from execution_testing.exceptions.exceptions import (
        TransactionException,
    )
    from execution_testing.specs.blockchain import Header


    @pytest.mark.exception_test
    def test_noop_rlp_modifier_tx_exception(blockchain_test, pre) -> None:
        tx = Transaction(
            to=0,
            gas_limit=21_000,
            gas_price=10**9,
            sender=pre.fund_eoa(amount=1),
            error=TransactionException.INSUFFICIENT_ACCOUNT_FUNDS,
        )
        blockchain_test(
            pre=pre,
            post={},
            blocks=[
                Block(
                    timestamp=12,
                    txs=[tx],
                    rlp_modifier=Header(timestamp=12),
                    exception=(
                        TransactionException.INSUFFICIENT_ACCOUNT_FUNDS
                    ),
                )
            ],
        )
    """
)


def test_fill_rejects_noop_rlp_modifier_on_invalid_block(
    pytester: Any, capsys: Any, pytestconfig: Any
) -> None:
    """A no-op modifier on an expected-invalid block must fail the fill."""
    tests_dir = pytester.mkdir("tests")
    cancun_tests_dir = tests_dir / "cancun"
    cancun_tests_dir.mkdir()
    module_dir = cancun_tests_dir / "noop_rlp_modifier_module"
    module_dir.mkdir()
    test_module = module_dir / "test_noop_rlp_modifier.py"
    test_module.write_text(noop_rlp_modifier_test_module)

    pytester.copy_example(
        name="src/execution_testing/cli/pytest_commands/pytest_ini_files/pytest-fill.ini"
    )

    result = pytester.runpytest_subprocess(
        "-c",
        "pytest-fill.ini",
        "--fork",
        "Cancun",
        "-m",
        "blockchain_test",
        "--no-html",
        "--output=stdout",
        str(test_module.relative_to(pytester.path)),
    )
    # Suppress the expected inner pytest failure output from the outer test
    capsys.readouterr()

    assert result.ret != 0, "Fill command was expected to fail"

    output = "\n".join(result.outlines + result.errlines)
    expected_message = "`rlp_modifier` changed nothing"
    assert expected_message in output

    error_line = next(
        line for line in output.splitlines() if expected_message in line
    )
    # show print but only when -s is passed
    if pytestconfig.getoption("capture") == "no":
        with capsys.disabled():
            print(error_line)


def test_fill_accepts_noop_rlp_modifier_on_tx_exception_block(
    pytester: Any,
) -> None:
    """
    A no-op modifier on a block whose invalidity comes from a
    transaction must fill: the block is invalid regardless of its
    header.
    """
    tests_dir = pytester.mkdir("tests")
    cancun_tests_dir = tests_dir / "cancun"
    cancun_tests_dir.mkdir()
    module_dir = cancun_tests_dir / "noop_rlp_modifier_tx_module"
    module_dir.mkdir()
    test_module = module_dir / "test_noop_rlp_modifier_tx_exception.py"
    test_module.write_text(noop_modifier_tx_exception_test_module)

    pytester.copy_example(
        name="src/execution_testing/cli/pytest_commands/pytest_ini_files/pytest-fill.ini"
    )

    result = pytester.runpytest_subprocess(
        "-c",
        "pytest-fill.ini",
        "--fork",
        "Cancun",
        "-m",
        "blockchain_test",
        "--no-html",
        "--output=stdout",
        str(test_module.relative_to(pytester.path)),
    )
    outcomes = result.parseoutcomes()
    assert outcomes.get("failed", 0) == 0
    assert outcomes.get("passed", 0) > 0
