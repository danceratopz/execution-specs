#!/usr/bin/env python3
r"""
Fan-in per-runner fixture artifacts into a single release tree.

The release workflow's ``combine`` job downloads each phase-2 runner's
``fixtures__<label>`` artifact into a distinct directory. This script
unions every per-runner tree into a single ``<combined>/`` directory and
regenerates ``<combined>/.meta/index.json`` from each split's own index
via ``IndexFile.merge`` (set-union over test cases, associative).

Replaces the bash ``cp -r`` loop plus a separate
``merge_index_files.py`` invocation: the fan-in and the index merge
always happen together, so fusing them keeps the workflow step to a
single line.

Usage::

    uv run python .github/scripts/fan_in_fixtures.py \
        <combined_dir> <split_dir>...
"""

import shutil
import sys
from pathlib import Path

from execution_testing.fixtures.consume import IndexFile


def union_into(combined: Path, split: Path) -> None:
    """Copy every entry of *split* into *combined*, merging directories."""
    for src in split.iterdir():
        dst = combined / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)


def merge_indexes(combined: Path, split_dirs: list[Path]) -> None:
    """Merge each split's ``.meta/index.json`` into *combined*."""
    indexes: list[IndexFile] = []
    for d in split_dirs:
        index_path = d / ".meta" / "index.json"
        if not index_path.exists():
            print(f"Skipping {d} (no .meta/index.json)")
            continue
        indexes.append(IndexFile.model_validate_json(index_path.read_text()))

    if not indexes:
        print("No split indexes found; combined index not regenerated.")
        return

    merged = IndexFile.merge(indexes)
    out_index = combined / ".meta" / "index.json"
    out_index.parent.mkdir(parents=True, exist_ok=True)
    out_index.write_text(merged.model_dump_json(indent=2))
    print(
        f"Merged {len(indexes)} index(es) into {out_index}"
        f" ({merged.test_count} tests)"
    )


def main() -> None:
    """Entry point."""
    if len(sys.argv) < 3:
        print(
            "Usage: fan_in_fixtures.py <combined_dir> <split_dir>...",
            file=sys.stderr,
        )
        sys.exit(1)

    combined = Path(sys.argv[1])
    split_dirs = [Path(d) for d in sys.argv[2:]]

    combined.mkdir(parents=True, exist_ok=True)
    seen: list[Path] = []
    for split in split_dirs:
        if not split.is_dir():
            print(f"Skipping missing split dir: {split}")
            continue
        union_into(combined, split)
        seen.append(split)

    if not seen:
        print("No split dirs provided; nothing to fan in.")
        return

    merge_indexes(combined, seen)


if __name__ == "__main__":
    main()
