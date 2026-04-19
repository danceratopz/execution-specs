"""
Test the CI release helper scripts.

Each test invokes the script via ``uv run`` to validate the actual CLI
interface, matching how GitHub Actions calls them.
"""

import importlib.util
import json
import os
import subprocess
import tarfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent

BUILD_MATRIX_SCRIPT = SCRIPTS_DIR / "generate_build_matrix.py"
TARBALL_SCRIPT = SCRIPTS_DIR / "create_release_tarball.py"
MERGE_INDEX_SCRIPT = SCRIPTS_DIR / "merge_index_files.py"
DOWNLOAD_DURATIONS_SCRIPT = SCRIPTS_DIR / "download_latest_durations.py"


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a uv inline-deps script and return the result."""
    return subprocess.run(
        ["uv", "run", "-q", str(script), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def parse_matrix_output(stdout: str) -> dict[str, str]:
    """Parse key=value output from generate_build_matrix.py."""
    return {
        k: v
        for line in stdout.strip().splitlines()
        if "=" in line
        for k, v in [line.split("=", 1)]
    }


_SPEC = importlib.util.spec_from_file_location(
    "generate_build_matrix", BUILD_MATRIX_SCRIPT
)
assert _SPEC is not None and _SPEC.loader is not None
gbm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gbm)


FORK_RANGES = [
    {"label": "pre-cancun", "from": "Frontier", "until": "Shanghai"},
    {"label": "cancun", "from": "Cancun", "until": "Cancun"},
    {"label": "prague", "from": "Prague", "until": "Prague"},
    {"label": "osaka", "from": "Osaka", "until": "Osaka"},
    {"label": "bpo", "from": "BPO1", "until": "BPO2"},
    {"label": "amsterdam", "from": "Amsterdam", "until": "Amsterdam"},
]


class TestGenerateBuildMatrixCLI:
    """CLI-level tests exercising real `.github/configs/feature.yaml`."""

    def test_mainnet_multi_range_unsplit_legacy(self):
        """--until=BPO2 without splits emits one entry per fork range."""
        result = run_script(BUILD_MATRIX_SCRIPT, "mainnet")
        assert result.returncode == 0
        out = parse_matrix_output(result.stdout)
        matrix = json.loads(out["build_matrix"])
        pre_alloc = json.loads(out["pre_alloc_matrix"])
        assert len(matrix) > 1
        assert pre_alloc == []
        assert out["pre_alloc_labels"] == ""
        assert out["feature_name"] == "mainnet"
        assert out["combine_labels"] != ""
        assert all(e["label"] for e in matrix)
        assert all(e["from_fork"] and e["until_fork"] for e in matrix)
        assert all(e["splits"] == 1 and e["group"] == 1 for e in matrix)

    def test_single_fork_unsplit_legacy(self):
        """--fork=X without splits emits one unsplit entry."""
        result = run_script(BUILD_MATRIX_SCRIPT, "benchmark")
        assert result.returncode == 0
        out = parse_matrix_output(result.stdout)
        matrix = json.loads(out["build_matrix"])
        pre_alloc = json.loads(out["pre_alloc_matrix"])
        assert len(matrix) == 1
        assert pre_alloc == []
        assert out["combine_labels"] == ""
        assert out["pre_alloc_labels"] == ""
        assert matrix[0]["label"] == ""
        assert matrix[0]["from_fork"] == ""
        assert matrix[0]["until_fork"] == ""
        assert matrix[0]["splits"] == 1
        assert matrix[0]["group"] == 1

    def test_unknown_feature_fails(self):
        """Verify error exit for unknown feature name."""
        result = run_script(BUILD_MATRIX_SCRIPT, "nonexistent")
        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_no_args_fails(self):
        """Verify error exit when no arguments provided."""
        result = run_script(BUILD_MATRIX_SCRIPT)
        assert result.returncode == 1
        assert "Usage" in result.stderr

    def test_output_is_valid_github_actions_format(self):
        """Verify output lines are key=value for GITHUB_OUTPUT."""
        result = run_script(BUILD_MATRIX_SCRIPT, "mainnet")
        assert result.returncode == 0
        lines = result.stdout.strip().splitlines()
        expected = [
            "build_matrix=",
            "pre_alloc_matrix=",
            "pre_alloc_labels=",
            "feature_name=",
            "combine_labels=",
        ]
        assert len(lines) == len(expected)
        for line, prefix in zip(lines, expected, strict=True):
            assert line.startswith(prefix)


class TestBuildMatrixShapes:
    """Unit tests over ``build_matrix()`` covering every split shape."""

    def test_until_multi_range_splits(self):
        """--until=X + splits>=2: per-range phase 1, per-group phase 2."""
        feature = {"fill-params": "--until=Osaka", "splits": 4}
        result = gbm.build_matrix(feature, "mainnet", FORK_RANGES)
        assert len(result["pre_alloc_matrix"]) == 4
        assert [e["label"] for e in result["pre_alloc_matrix"]] == [
            "pre-cancun",
            "cancun",
            "prague",
            "osaka",
        ]
        assert result["pre_alloc_labels"] == ("pre-cancun cancun prague osaka")
        assert len(result["build_matrix"]) == 4
        assert [e["group"] for e in result["build_matrix"]] == [1, 2, 3, 4]
        assert all(e["splits"] == 4 for e in result["build_matrix"])
        assert all(
            e["from_fork"] == "" and e["until_fork"] == ""
            for e in result["build_matrix"]
        )
        assert result["combine_labels"] == "1 2 3 4"

    def test_single_fork_splits(self):
        """--fork=X + splits>=2: single phase 1, per-group phase 2."""
        feature = {"fill-params": "--fork=Osaka", "splits": 3}
        result = gbm.build_matrix(feature, "benchmark", FORK_RANGES)
        assert len(result["pre_alloc_matrix"]) == 1
        assert result["pre_alloc_matrix"][0]["label"] == "osaka"
        assert result["pre_alloc_matrix"][0]["from_fork"] == ""
        assert result["pre_alloc_matrix"][0]["until_fork"] == ""
        assert result["pre_alloc_labels"] == "osaka"
        assert len(result["build_matrix"]) == 3
        assert [e["group"] for e in result["build_matrix"]] == [1, 2, 3]
        assert result["combine_labels"] == "1 2 3"

    def test_single_fork_single_split_legacy(self):
        """--fork=X + splits=1: single unsplit entry, no phase 1."""
        feature = {"fill-params": "--fork=Amsterdam", "splits": 1}
        result = gbm.build_matrix(feature, "bal", FORK_RANGES)
        assert result["pre_alloc_matrix"] == []
        assert result["pre_alloc_labels"] == ""
        assert len(result["build_matrix"]) == 1
        entry = result["build_matrix"][0]
        assert entry == {
            "feature": "bal",
            "label": "",
            "from_fork": "",
            "until_fork": "",
            "splits": 1,
            "group": 1,
        }
        assert result["combine_labels"] == ""

    def test_until_clamps_to_final_range(self):
        """Ranges beyond --until are clamped and dropped."""
        feature = {"fill-params": "--until=Cancun", "splits": 2}
        result = gbm.build_matrix(feature, "mainnet", FORK_RANGES)
        assert [e["label"] for e in result["pre_alloc_matrix"]] == [
            "pre-cancun",
            "cancun",
        ]

    def test_splits_default_is_one(self):
        """A feature without an explicit splits field falls back to 1."""
        feature = {"fill-params": "--fork=Osaka"}
        result = gbm.build_matrix(feature, "benchmark", FORK_RANGES)
        assert result["pre_alloc_matrix"] == []
        assert len(result["build_matrix"]) == 1
        assert result["build_matrix"][0]["splits"] == 1


class TestCreateReleaseTarball:
    """Test create_release_tarball.py."""

    def test_tarball_structure(self, tmp_path):
        """Verify tarball has fixtures/ prefix and correct contents."""
        src = tmp_path / "fixtures"
        (src / "blockchain_tests" / "for_cancun").mkdir(parents=True)
        (src / "blockchain_tests_engine_x" / "pre_alloc").mkdir(parents=True)
        (src / ".meta").mkdir()

        (src / "blockchain_tests" / "for_cancun" / "t.json").write_text("{}")
        pre_alloc = src / "blockchain_tests_engine_x" / "pre_alloc"
        (pre_alloc / "g.json").write_text("{}")
        (src / ".meta" / "fixtures.ini").write_text("[meta]")

        out = tmp_path / "output.tar.gz"
        result = run_script(TARBALL_SCRIPT, str(src), str(out))
        assert result.returncode == 0
        assert out.exists()

        with tarfile.open(out, "r:gz") as tar:
            names = sorted(tar.getnames())

        assert all(n.startswith("fixtures/") for n in names)
        assert "fixtures/blockchain_tests/for_cancun/t.json" in names
        assert "fixtures/blockchain_tests_engine_x/pre_alloc/g.json" in names
        assert "fixtures/.meta/fixtures.ini" in names

    def test_excludes_non_fixture_files(self, tmp_path):
        """Verify .log, .html, etc. are excluded from tarball."""
        src = tmp_path / "fixtures"
        src.mkdir()
        (src / "test.json").write_text("{}")
        (src / "debug.log").write_text("log")
        (src / "report.html").write_text("<html>")
        (src / "data.csv").write_text("a,b")

        out = tmp_path / "output.tar.gz"
        result = run_script(TARBALL_SCRIPT, str(src), str(out))
        assert result.returncode == 0

        with tarfile.open(out, "r:gz") as tar:
            names = tar.getnames()

        assert "fixtures/test.json" in names
        assert len(names) == 1

    def test_nonexistent_dir_fails(self, tmp_path):
        """Verify error for non-existent source directory."""
        result = run_script(
            TARBALL_SCRIPT,
            str(tmp_path / "nope"),
            str(tmp_path / "out.tar.gz"),
        )
        assert result.returncode == 1
        assert "not a directory" in result.stderr

    def test_no_args_fails(self):
        """Verify error when no arguments provided."""
        result = run_script(TARBALL_SCRIPT)
        assert result.returncode == 1
        assert "Usage" in result.stderr


def _run_merge_script(
    *args: str,
) -> subprocess.CompletedProcess:
    """Run merge_index_files.py via uv run python."""
    return subprocess.run(
        ["uv", "run", "python", str(MERGE_INDEX_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


class TestMergeIndexFiles:
    """Test merge_index_files.py."""

    def _write_index(self, fixture_dir: Path, index_data: dict) -> None:
        """Write a .meta/index.json file in the given directory."""
        meta = fixture_dir / ".meta"
        meta.mkdir(parents=True, exist_ok=True)
        (meta / "index.json").write_text(json.dumps(index_data))

    def test_merges_two_index_files(self, tmp_path):
        """Verify merging two fixture dirs produces a combined index."""
        dir_a = tmp_path / "fixtures__cancun"
        dir_b = tmp_path / "fixtures__prague"
        output = tmp_path / "combined" / ".meta" / "index.json"

        self._write_index(
            dir_a,
            {
                "root_hash": None,
                "created_at": "2026-01-01T00:00:00",
                "test_count": 1,
                "forks": ["Cancun"],
                "fixture_formats": ["state_test"],
                "test_cases": [
                    {
                        "id": "test_a",
                        "json_path": "state_tests/for_cancun/t.json",
                        "fixture_hash": "0x" + "11" * 32,
                        "fork": "Cancun",
                        "format": "state_test",
                    }
                ],
            },
        )
        self._write_index(
            dir_b,
            {
                "root_hash": None,
                "created_at": "2026-01-01T00:00:00",
                "test_count": 1,
                "forks": ["Prague"],
                "fixture_formats": ["blockchain_test"],
                "test_cases": [
                    {
                        "id": "test_b",
                        "json_path": "blockchain_tests/for_prague/t.json",
                        "fixture_hash": "0x" + "22" * 32,
                        "fork": "Prague",
                        "format": "blockchain_test",
                    }
                ],
            },
        )

        result = _run_merge_script(
            str(output),
            str(dir_a),
            str(dir_b),
        )
        assert result.returncode == 0
        assert output.exists()

        merged = json.loads(output.read_text())
        assert merged["test_count"] == 2
        assert len(merged["test_cases"]) == 2
        assert merged["root_hash"] is not None

    def test_skips_dirs_without_index(self, tmp_path):
        """Verify directories without .meta/index.json are skipped."""
        dir_a = tmp_path / "fixtures__cancun"
        dir_a.mkdir()
        dir_b = tmp_path / "fixtures__empty"
        dir_b.mkdir()
        output = tmp_path / "out.json"

        self._write_index(
            dir_a,
            {
                "root_hash": None,
                "created_at": "2026-01-01T00:00:00",
                "test_count": 1,
                "forks": ["Cancun"],
                "fixture_formats": ["state_test"],
                "test_cases": [
                    {
                        "id": "test_a",
                        "json_path": "state_tests/t.json",
                        "fixture_hash": "0x" + "11" * 32,
                        "fork": "Cancun",
                        "format": "state_test",
                    }
                ],
            },
        )

        result = _run_merge_script(str(output), str(dir_a), str(dir_b))
        assert result.returncode == 0
        assert output.exists()

        merged = json.loads(output.read_text())
        assert merged["test_count"] == 1

    def test_no_args_fails(self):
        """Verify error when no arguments provided."""
        result = _run_merge_script()
        assert result.returncode == 1
        assert "Usage" in result.stderr


FAKE_GH_SOURCE = '''#!/usr/bin/env python3
"""Fake `gh` CLI stub driven by files in $GH_FAKE_STATE_DIR."""

import os
import sys
from pathlib import Path

state = Path(os.environ["GH_FAKE_STATE_DIR"])

if sys.argv[1] == "api":
    rc = int((state / "api_rc.txt").read_text())
    if rc == 0:
        sys.stdout.write((state / "api_payload.txt").read_text())
    else:
        sys.stderr.write("gh api failed\\n")
    sys.exit(rc)

if sys.argv[1:3] == ["run", "download"]:
    rc = int((state / "download_rc.txt").read_text())
    creates = (state / "download_creates_file.txt").read_text() == "1"
    if rc == 0 and creates:
        dir_idx = sys.argv.index("--dir")
        target = Path(sys.argv[dir_idx + 1])
        (target / ".test_durations").write_text("{}")
    if rc != 0:
        sys.stderr.write("gh run download failed\\n")
    sys.exit(rc)

sys.exit(2)
'''


class TestDownloadLatestDurations:
    """Exercise download_latest_durations.py via fake `gh` on PATH."""

    def _setup(
        self,
        tmp_path,
        *,
        api_payload='{"artifacts": []}',
        api_rc=0,
        download_rc=0,
        download_creates_file=False,
    ):
        """Create fake gh + state dir. Return (bin_dir, state, cwd)."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        state = tmp_path / "state"
        state.mkdir()
        cwd = tmp_path / "work"
        cwd.mkdir()

        (state / "api_payload.txt").write_text(api_payload)
        (state / "api_rc.txt").write_text(str(api_rc))
        (state / "download_rc.txt").write_text(str(download_rc))
        (state / "download_creates_file.txt").write_text(
            "1" if download_creates_file else "0"
        )

        gh = bin_dir / "gh"
        gh.write_text(FAKE_GH_SOURCE)
        gh.chmod(0o755)
        return bin_dir, state, cwd

    def _run(self, tmp_path, bin_dir, state, cwd, *, repo="owner/repo"):
        """Run the script with fake gh on PATH; return (result, summary)."""
        summary = tmp_path / "step_summary.md"
        summary.write_text("")
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env["GH_FAKE_STATE_DIR"] = str(state)
        env["GITHUB_STEP_SUMMARY"] = str(summary)
        if repo is not None:
            env["GITHUB_REPOSITORY"] = repo
        result = subprocess.run(
            [
                "uv",
                "run",
                "-q",
                str(DOWNLOAD_DURATIONS_SCRIPT),
                "mainnet",
            ],
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
        )
        return result, summary

    def test_no_prior_artifact_warns(self, tmp_path):
        """Empty artifact list emits warning; no .test_durations created."""
        bin_dir, state, cwd = self._setup(tmp_path)
        result, summary = self._run(tmp_path, bin_dir, state, cwd)

        assert result.returncode == 0
        assert "::warning::" in result.stderr
        assert not (cwd / ".test_durations").exists()
        assert "No previous" in summary.read_text()

    def test_successful_download_populates_file(self, tmp_path):
        """Matching artifact => .test_durations downloaded; summary set."""
        payload = json.dumps({"artifacts": [{"workflow_run": {"id": 4242}}]})
        bin_dir, state, cwd = self._setup(
            tmp_path,
            api_payload=payload,
            download_creates_file=True,
        )
        result, summary = self._run(tmp_path, bin_dir, state, cwd)

        assert result.returncode == 0
        assert (cwd / ".test_durations").exists()
        text = summary.read_text()
        assert "Downloaded" in text
        assert "4242" in text

    def test_gh_api_failure_warns(self, tmp_path):
        """Nonzero gh api exit => warning + clean exit."""
        bin_dir, state, cwd = self._setup(tmp_path, api_rc=1)
        result, _ = self._run(tmp_path, bin_dir, state, cwd)

        assert result.returncode == 0
        assert "::warning::" in result.stderr
        assert not (cwd / ".test_durations").exists()

    def test_missing_repo_env_errors(self, tmp_path):
        """Missing GITHUB_REPOSITORY => nonzero exit."""
        bin_dir, state, cwd = self._setup(tmp_path)
        result, _ = self._run(tmp_path, bin_dir, state, cwd, repo=None)

        assert result.returncode == 1
        assert "GITHUB_REPOSITORY" in result.stderr

    def test_no_args_fails(self):
        """Verify error when no feature arg provided."""
        result = run_script(DOWNLOAD_DURATIONS_SCRIPT)
        assert result.returncode == 1
        assert "Usage" in result.stderr
