"""
Test the eligibility markers' interaction with the prepended empty
block.

A marked test cannot survive the prepend transformation: the prepended
block shifts every position, so the fixture would verify something
other than what the test author wrote. A marked test is not skipped -
it fills without the extra block, so no test ever leaves the fixture
release; sync-based consumers skip its single-block chain at consume
time instead.
"""

import json
import textwrap
from pathlib import Path
from typing import Any, Dict

import pytest

marked_test_module = textwrap.dedent(
    """\
    import pytest

    from execution_testing import Block, Transaction


    @pytest.mark.{marker}
    def test_marked(blockchain_test, pre) -> None:
        tx = Transaction(
            to=0,
            gas_limit=21_000,
            sender=pre.fund_eoa(),
        )
        blockchain_test(pre=pre, post={{}}, blocks=[Block(txs=[tx])])


    def test_unmarked(blockchain_test, pre) -> None:
        tx = Transaction(
            to=0,
            gas_limit=21_000,
            sender=pre.fund_eoa(),
        )
        blockchain_test(pre=pre, post={{}}, blocks=[Block(txs=[tx])])
    """
)


def make_test_module(pytester: Any, marker: str) -> Any:
    """Write a test module into a pytester tests tree."""
    tests_dir = pytester.mkdir("tests")
    cancun_tests_dir = tests_dir / "cancun"
    cancun_tests_dir.mkdir()
    module_dir = cancun_tests_dir / "prepend_empty_block_markers_module"
    module_dir.mkdir()
    test_module = module_dir / "test_marked.py"
    test_module.write_text(marked_test_module.format(marker=marker))
    pytester.copy_example(
        name="src/execution_testing/cli/pytest_commands/pytest_ini_files/pytest-fill.ini"
    )
    return test_module


def fill(pytester: Any, test_module: Any) -> Path:
    """Fill the module in both phases and return the output directory."""
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
    result = pytester.runpytest_subprocess("--use-pre-alloc-groups", *common)
    assert result.ret == 0, "fill phase 2 was expected to succeed"
    return output


def engine_x_fixtures(output: Path) -> Dict[str, Dict[str, Any]]:
    """Return the emitted engine_x fixtures keyed by test id."""
    fixtures: Dict[str, Dict[str, Any]] = {}
    for path in sorted((output / "blockchain_tests_engine_x").rglob("*.json")):
        if "pre_alloc" in path.parts:
            continue
        fixtures.update(json.loads(path.read_text()))
    assert fixtures, "no engine_x fixtures were emitted"
    return fixtures


@pytest.mark.parametrize(
    "marker",
    [
        "absolute_block_position",
    ],
)
def test_marked_test_fills_without_the_prepended_block(
    pytester: Any, marker: str
) -> None:
    """
    Each marker must veto the prepend for its own test only: the
    marked test fills with exactly its own single block while the
    unmarked test in the same module gains the prepended one.
    """
    test_module = make_test_module(pytester, marker=marker)
    output = fill(pytester, test_module)

    fixtures = engine_x_fixtures(output)
    by_name = {
        ("marked" if "test_marked[" in test_id else "unmarked"): fixture
        for test_id, fixture in fixtures.items()
    }
    assert set(by_name) == {"marked", "unmarked"}

    marked_payloads = by_name["marked"]["engineNewPayloads"]
    assert len(marked_payloads) == 1, (
        "the marked test must fill without the prepended block"
    )
    assert marked_payloads[0].get("phase") is None

    unmarked_payloads = by_name["unmarked"]["engineNewPayloads"]
    assert len(unmarked_payloads) == 2, (
        "the unmarked test must still gain the prepended block"
    )
    assert unmarked_payloads[0].get("phase") == "sync"
