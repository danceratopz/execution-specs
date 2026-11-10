"""
Test how the grouped formats fill a test against its pre-allocation group.

`blockchain_test_x` fills the forks before Paris and
`blockchain_test_engine_x` those from Paris on, both against the genesis
of the test's pre-allocation group. These tests fill a module across the
boundary in both phases and read the fixtures and the group files back.
"""

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List

import pytest

TEST_MODULE = textwrap.dedent(
    """\
    import pytest

    from execution_testing import Block, Transaction


    def test_shared(blockchain_test, pre) -> None:
        tx = Transaction(
            to=0, value=1, gas_limit=21_000, sender=pre.fund_eoa(),
            protected=False,
        )
        blockchain_test(pre=pre, post={}, blocks=[Block(txs=[tx])])


    @pytest.mark.pre_alloc_group("separate", reason="own genesis")
    def test_separate(blockchain_test, pre) -> None:
        tx = Transaction(
            to=0, value=2, gas_limit=21_000, sender=pre.fund_eoa(),
            protected=False,
        )
        blockchain_test(pre=pre, post={}, blocks=[Block(txs=[tx])])
    """
)

GROUPED_FORMATS = {
    "blockchain_tests_engine_x": "blockchain_test_engine_x",
    "blockchain_tests_x": "blockchain_test_x",
}


MODULE_PATH = "tests/frontier/grouped_module/test_grouped.py"


def fill(pytester: pytest.Pytester, *args: str) -> Path:
    """
    Fill the module in both phases for London and Paris, the last fork
    before the merge and the first after it, and return the output
    directory.
    """
    test_module = pytester.path / MODULE_PATH
    test_module.parent.mkdir(parents=True)
    test_module.write_text(TEST_MODULE)
    pytester.copy_example(
        name="src/execution_testing/cli/pytest_commands/pytest_ini_files/pytest-fill.ini"
    )
    output = pytester.path / "fixtures"
    common = (
        "-c",
        "pytest-fill.ini",
        "--from",
        "London",
        "--until",
        "Paris",
        "--skip-index",
        "--no-html",
        f"--output={output}",
        "--generate-all-formats",
        *args,
        str(test_module.relative_to(pytester.path)),
    )
    result = pytester.runpytest("--generate-pre-alloc-groups", *common)
    assert result.ret == 0, "fill phase 1 was expected to succeed"
    result = pytester.runpytest("--use-pre-alloc-groups", *common)
    assert result.ret == 0, "fill phase 2 was expected to succeed"
    return output


def grouped_fixtures(output: Path) -> Dict[str, Dict[str, Any]]:
    """Return every grouped fixture keyed by its test id."""
    fixtures: Dict[str, Dict[str, Any]] = {}
    for format_dir in GROUPED_FORMATS:
        for path in (output / format_dir).rglob("*.json"):
            if "pre_alloc" not in path.parts:
                fixtures.update(json.loads(path.read_text()))
    return fixtures


def groups(output: Path) -> List[Dict[str, Any]]:
    """Return the pre-allocation group files of the fill."""
    folder = output / "blockchain_tests_engine_x" / "pre_alloc"
    return [json.loads(path.read_text()) for path in folder.glob("*.json")]


def genesis_hash(fixture: Dict[str, Any]) -> str:
    """Return the hash of the genesis the fixture's first block builds on."""
    if "genesisBlockHeader" in fixture:
        return fixture["genesisBlockHeader"]["hash"]
    return fixture["engineNewPayloads"][0]["params"][0]["parentHash"]


def group_of(test_id: str, all_groups: List[Dict[str, Any]]) -> Any:
    """Return the group whose test ids include the fixture's test id."""
    matches = [group for group in all_groups if test_id in group["testIds"]]
    assert len(matches) == 1, f"{test_id} is in {len(matches)} groups"
    return matches[0]


def test_each_fork_fills_one_grouped_format(pytester: pytest.Pytester) -> None:
    """
    London fills only `blockchain_test_x`, Paris only
    `blockchain_test_engine_x`. Each test sits in one group per fork, once,
    by the id of its grouped fixture, and that fixture starts from the
    group's genesis.
    """
    output = fill(pytester)
    fixtures = grouped_fixtures(output)
    all_groups = groups(output)

    assert sorted(fixtures) == sorted(
        f"{MODULE_PATH}::{test_name}[fork_{fork}-{format_name}]"
        for test_name in ("test_shared", "test_separate")
        for fork, format_name in [
            ("London", "blockchain_test_x"),
            ("Paris", "blockchain_test_engine_x"),
        ]
    )
    assert len(all_groups) == 4, "one group per fork for each test"
    for group in all_groups:
        assert group["testCount"] == 1
        assert len(group["testIds"]) == 1

    for test_id, fixture in fixtures.items():
        group = group_of(test_id, all_groups)
        assert fixture["preHash"] == group["groupHash"]
        assert genesis_hash(fixture) == group["genesis"]["hash"]


@pytest.mark.parametrize(
    "marker, fork",
    [("blockchain_test_engine_x", "Paris"), ("blockchain_test_x", "London")],
)
def test_selecting_one_grouped_format(
    pytester: pytest.Pytester, marker: str, fork: str
) -> None:
    """
    A `-m` selection reaches phase 1 too: phase 1 registers exactly the
    tests of the forks the selected grouped format fills.
    """
    output = fill(pytester, "-m", marker)
    fixtures = grouped_fixtures(output)

    assert len(fixtures) == 2
    assert all(f"[fork_{fork}-{marker}]" in test_id for test_id in fixtures)
    all_groups = groups(output)
    assert len(all_groups) == 2
    for test_id, fixture in fixtures.items():
        assert fixture["preHash"] == group_of(test_id, all_groups)["groupHash"]
