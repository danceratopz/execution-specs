"""
Test the ``absolute_block_position`` marker's interaction with the
``--prepend-empty-block`` fill option.

Tests whose logic or expectations depend on absolute block numbers or
block hashes cannot survive the prepend transformation: the prepended
block shifts every position, so the fixture would verify something
other than what the test author wrote. Marked tests are skipped when
the option is given and fill normally without it.
"""

import textwrap
from typing import Any

absolute_block_position_test_module = textwrap.dedent(
    """\
    import pytest

    from execution_testing import Block, Transaction


    @pytest.mark.absolute_block_position
    def test_absolute_number(blockchain_test, pre) -> None:
        tx = Transaction(
            to=0,
            gas_limit=21_000,
            sender=pre.fund_eoa(),
        )
        blockchain_test(pre=pre, post={}, blocks=[Block(txs=[tx])])
    """
)


def make_test_module(pytester: Any) -> Any:
    """Write the marked test module into a pytester tests tree."""
    tests_dir = pytester.mkdir("tests")
    cancun_tests_dir = tests_dir / "cancun"
    cancun_tests_dir.mkdir()
    module_dir = cancun_tests_dir / "absolute_block_position_module"
    module_dir.mkdir()
    test_module = module_dir / "test_absolute_number.py"
    test_module.write_text(absolute_block_position_test_module)
    pytester.copy_example(
        name="src/execution_testing/cli/pytest_commands/pytest_ini_files/pytest-fill.ini"
    )
    return test_module


def test_marked_test_skips_with_prepend_empty_block(pytester: Any) -> None:
    """The marked test must be skipped when the option is given."""
    test_module = make_test_module(pytester)
    result = pytester.runpytest_subprocess(
        "-c",
        "pytest-fill.ini",
        "--fork",
        "Cancun",
        "-m",
        "blockchain_test",
        "--prepend-empty-block",
        "-rs",
        "--no-html",
        "--output=stdout",
        str(test_module.relative_to(pytester.path)),
    )
    # The custom report plugin counts the teardown of a setup-skipped
    # item as passed, so only the skip count is meaningful here; the
    # skip itself proves no fixture was filled for the marked test.
    outcomes = result.parseoutcomes()
    assert outcomes.get("skipped", 0) > 0
    result.stdout.fnmatch_lines(["*test depends on absolute block positions*"])


def test_marked_test_fills_without_prepend_empty_block(pytester: Any) -> None:
    """The marked test must fill normally without the option."""
    test_module = make_test_module(pytester)
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
    assert outcomes.get("passed", 0) > 0
    assert outcomes.get("skipped", 0) == 0
