#!/usr/bin/env python3
"""
Merge the fixture indexes of two fixture images of the same release.

Each fixture image carries the index of its own format (see
`packages/testing/docker/fixtures/subset_index.py`). A simulator image that
carries two formats needs one index that lists the test cases of both: this
writes the first index with the second's test cases appended, and with
test_count, fixture_formats and forks recomputed. root_hash stays cleared.

Standard library only, so that this runs in any Python base image.
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    """Write the merged index."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("first", type=Path, help="index.json of one format")
    parser.add_argument("second", type=Path, help="index.json of another")
    parser.add_argument("output", type=Path, help="merged index.json")
    args = parser.parse_args()

    index = json.loads(args.first.read_text())
    second = json.loads(args.second.read_text())
    paths = {case["json_path"] for case in index["test_cases"]}
    shared = [
        case["json_path"]
        for case in second["test_cases"]
        if case["json_path"] in paths
    ]
    if shared:
        print(
            f"error: both indexes list {len(shared)} fixture files, "
            f"e.g. {shared[0]}",
            file=sys.stderr,
        )
        return 1

    index["test_cases"] += second["test_cases"]
    index["test_count"] = len(index["test_cases"])
    index["fixture_formats"] = sorted(
        {*index["fixture_formats"], *second["fixture_formats"]}
    )
    index["forks"] = sorted(
        {*(index.get("forks") or []), *(second.get("forks") or [])}
    )
    index["root_hash"] = None

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(index) + "\n")
    print(
        f"merged {index['test_count']} test cases; "
        f"formats {index['fixture_formats']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
