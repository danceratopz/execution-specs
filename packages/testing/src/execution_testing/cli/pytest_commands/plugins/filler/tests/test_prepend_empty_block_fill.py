"""
Test that the prepended empty block reaches exactly the fixture
formats that opt in.

The prepend is scoped per fixture format: only
``blockchain_test_engine_x`` declares ``prepend_empty_block`` true, so
a fill with the option must emit engine_x chains with one extra
leading block - tagged with the ``sync`` phase - while every other
format's chains are byte-for-byte what the test defines. These tests
fill a single-block test and read the fixtures back, so a prepend
that leaks into the wrong format, loses its phase tag, or fails to
salt per test fails here rather than in a consumer.
"""

import json
import textwrap
from pathlib import Path
from typing import Any, Dict

single_block_test_module = textwrap.dedent(
    """\
    import pytest

    from execution_testing import Block, Transaction


    # Two tests of one pre-allocation group: a client reused across
    # them must not already know either prepended block.
    @pytest.mark.parametrize("value", [1, 2])
    def test_single_block(blockchain_test, pre, value) -> None:
        tx = Transaction(
            to=0,
            value=value,
            gas_limit=21_000,
            sender=pre.fund_eoa(),
        )
        blockchain_test(pre=pre, post={}, blocks=[Block(txs=[tx])])
    """
)


def make_test_module(pytester: Any) -> Any:
    """Write the single-block test module into a pytester tests tree."""
    tests_dir = pytester.mkdir("tests")
    cancun_tests_dir = tests_dir / "cancun"
    cancun_tests_dir.mkdir()
    module_dir = cancun_tests_dir / "prepend_empty_block_fill_module"
    module_dir.mkdir()
    test_module = module_dir / "test_single_block.py"
    test_module.write_text(single_block_test_module)
    pytester.copy_example(
        name="src/execution_testing/cli/pytest_commands/pytest_ini_files/pytest-fill.ini"
    )
    return test_module


def fill(pytester: Any, test_module: Any, *args: str) -> Path:
    """
    Fill the module's engine_x fixtures into a fresh output directory
    and return it.

    An all-formats fill is two pytest sessions - the `fill` CLI runs
    phase 1 (pre-allocation grouping) and phase 2 (fixture filling)
    back to back - so both are run here the same way.
    """
    output = pytester.path / f"fixtures{len(args)}"
    common = (
        "-c",
        "pytest-fill.ini",
        "--fork",
        "Cancun",
        "--generate-all-formats",
        "-m",
        "blockchain_test_engine_x",
        "--skip-index",
        "--no-html",
        f"--output={output}",
        *args,
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


def test_prepended_block_reaches_the_engine_x_fixtures(
    pytester: Any,
) -> None:
    """
    Engine X chains gain one empty block ahead of the test's own,
    tagged with the sync phase.
    """
    test_module = make_test_module(pytester)
    output = fill(pytester, test_module, "--prepend-empty-block")

    for fixture in engine_x_fixtures(output).values():
        payloads = fixture["engineNewPayloads"]
        assert len(payloads) == 2
        prepended, own = (payload["params"][0] for payload in payloads)
        assert payloads[0].get("phase") == "sync", (
            "the prepended payload must carry the sync phase tag"
        )
        assert payloads[1].get("phase") is None
        assert prepended["transactions"] == [], (
            "the prepended block carries no transactions"
        )
        assert int(prepended["blockNumber"], 16) == 1
        assert len(prepended["extraData"]) == 2 + 2 * 16, (
            "the prepended block is salted with a digest of the test id"
        )
        assert own["parentHash"] == prepended["blockHash"]


def test_prepended_block_is_salted_per_test(pytester: Any) -> None:
    """
    Each test's prepended block must be unique to it, or a client
    reused across a pre-allocation group already knows the second
    test's head parent and no sync is triggered.
    """
    test_module = make_test_module(pytester)
    output = fill(pytester, test_module, "--prepend-empty-block")

    salted = {
        fixture["engineNewPayloads"][0]["params"][0]["extraData"]
        for fixture in engine_x_fixtures(output).values()
    }
    assert len(salted) == 2


def test_fixtures_are_unchanged_without_the_option(pytester: Any) -> None:
    """Without the option no format gains the extra block."""
    test_module = make_test_module(pytester)
    output = fill(pytester, test_module)

    for fixture in engine_x_fixtures(output).values():
        payloads = fixture["engineNewPayloads"]
        assert len(payloads) == 1
        assert payloads[0].get("phase") is None
