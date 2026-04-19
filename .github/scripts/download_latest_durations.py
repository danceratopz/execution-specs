#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Download the most recent ``durations_<feature>`` artifact for a release
feature from any prior workflow run in the current repository.

The current workflow has not produced a durations artifact yet (the
phase-2 runners are about to produce one), so ``actions/download-
artifact`` cannot find it. Query the GitHub Actions artifacts API for
the most recent match across all runs, then pull its contents down
into the current working directory via ``gh run download``.

Missing or failed downloads are a warning rather than a fatal error:
the grouped-split plugin silently falls back to average-only
bin-packing when ``.test_durations`` is absent, and the ``::warning::``
annotation in the job summary surfaces the degradation.

Usage::

    uv run -q .github/scripts/download_latest_durations.py <feature>
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def _gh(*args: str) -> subprocess.CompletedProcess[str]:
    """Run ``gh`` capturing stdout/stderr as text."""
    return subprocess.run(
        ["gh", *args],
        check=False,
        text=True,
        capture_output=True,
    )


def _warn(message: str) -> None:
    """Emit a GitHub Actions warning annotation on stderr."""
    print(f"::warning::{message}", file=sys.stderr)


def _step_summary(line: str) -> None:
    """Append a line to ``GITHUB_STEP_SUMMARY`` when set."""
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        Path(summary).open("a").write(line + "\n")


def latest_run_id(repo: str, artifact_name: str) -> str | None:
    """
    Return the most recent workflow-run id that uploaded *artifact_name*.

    Returns ``None`` when the API has no matching artifact — either the
    first run of a feature, or the retention window has expired.
    """
    result = _gh(
        "api",
        f"repos/{repo}/actions/artifacts?name={artifact_name}&per_page=1",
    )
    if result.returncode != 0:
        _warn(
            f"gh api failed for artifacts?name={artifact_name}:"
            f" {result.stderr.strip()}"
        )
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        _warn(f"gh api returned non-JSON for {artifact_name}: {exc}")
        return None
    artifacts = payload.get("artifacts") or []
    if not artifacts:
        return None
    return str(artifacts[0]["workflow_run"]["id"])


def main() -> None:
    """Entry point."""
    if len(sys.argv) != 2:
        print(
            "Usage: download_latest_durations.py <feature>",
            file=sys.stderr,
        )
        sys.exit(1)

    feature = sys.argv[1]
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print(
            "Error: GITHUB_REPOSITORY env var is required.",
            file=sys.stderr,
        )
        sys.exit(1)

    artifact = f"durations_{feature}"
    run_id = latest_run_id(repo, artifact)
    if run_id is None:
        _warn(
            f"No previous {artifact} artifact found; grouped-split will"
            " fall back to average-only bin-packing."
        )
        _step_summary(
            f"### Durations\nNo previous `{artifact}` found; using"
            " average-only bin-packing."
        )
        return

    print(f"Downloading {artifact} from run {run_id}")
    result = _gh(
        "run",
        "download",
        run_id,
        "-n",
        artifact,
        "--dir",
        ".",
    )
    if result.returncode != 0:
        _warn(
            f"gh run download failed for {artifact} (run {run_id}):"
            f" {result.stderr.strip()}"
        )
        _step_summary(
            f"### Durations\nDownload of `{artifact}` from run"
            f" [{run_id}](/{repo}/actions/runs/{run_id}) failed; using"
            " average-only bin-packing."
        )
        return

    durations_path = Path(".test_durations")
    if not durations_path.exists():
        _warn(
            f"Downloaded {artifact} but .test_durations is missing at"
            " the expected path."
        )
        return

    size = durations_path.stat().st_size
    print(f"Downloaded .test_durations ({size} bytes)")
    _step_summary(
        f"### Durations\nDownloaded `{artifact}` from run"
        f" [{run_id}](/{repo}/actions/runs/{run_id}) ({size} bytes)."
    )


if __name__ == "__main__":
    main()
