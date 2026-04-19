#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pyyaml",
# ]
# ///
"""
Generate build matrices for release fixture workflows.

Read `.github/configs/feature.yaml` and emit JSON build matrices
suitable for ``strategy.matrix`` in GitHub Actions.

Emits four outputs:

- ``build_matrix``   : phase-2 (fill) entries.
- ``pre_alloc_matrix``: phase-1 (pre-alloc generation) entries. Empty
  when the feature does not split across runners.
- ``pre_alloc_labels``: space-separated phase-1 labels, used by the
  build job to download every pre-alloc artifact.
- ``combine_labels``  : space-separated phase-2 labels, used by the
  combine job to fan in per-runner fixture and durations artifacts.

Matrix shape rules:

- ``splits >= 2`` (pytest-split parallelism):
  - Phase 1 runs once per fork range for ``--until=X`` features, or
    once for ``--fork=X`` features. Pre-alloc groups are an artifact
    shared by every phase-2 runner.
  - Phase 2 runs ``splits`` jobs, each filling one ``--group`` of the
    grouped-split partition over the full feature scope. No fork-range
    axis: the plugin balances across forks within one pytest session.
- ``splits < 2`` (legacy unsplit):
  - Phase 1 is skipped entirely; fill runs its own internal two-phase
    flow on each phase-2 runner.
  - Phase 2 matches the pre-pytest-split behaviour: one entry per
    applicable fork range for ``--until=X``, otherwise one unsplit
    entry.
"""

import json
import re
import sys
from pathlib import Path

import yaml

FEATURE_CONFIG = Path(".github/configs/feature.yaml")
FORK_RANGES_CONFIG = Path(".github/configs/fork-ranges.yaml")

# Canonical fork ordering used to filter fork ranges per feature.
FORK_ORDER = [
    "Frontier",
    "Homestead",
    "DAOFork",
    "TangerineWhistle",
    "SpuriousDragon",
    "Byzantium",
    "Constantinople",
    "Istanbul",
    "MuirGlacier",
    "Berlin",
    "London",
    "ArrowGlacier",
    "GrayGlacier",
    "Paris",
    "Shanghai",
    "Cancun",
    "Prague",
    "Osaka",
    "BPO1",
    "BPO2",
    "Amsterdam",
]

FORK_INDEX = {name: i for i, name in enumerate(FORK_ORDER)}


def load_config(path: Path) -> dict | list:
    """Load and return a YAML configuration file."""
    with open(path) as f:
        return yaml.safe_load(f)


def parse_fork_arg(fill_params: str) -> str | None:
    """Extract the ``--fork`` value from *fill_params*."""
    m = re.search(r"--fork[=\s]+(\S+)", fill_params)
    return m.group(1) if m else None


def parse_until_fork(fill_params: str) -> str | None:
    """
    Extract the ``--until`` value from *fill_params*.

    Return ``None`` when ``--fork`` is used (single-fork feature).
    """
    if re.search(r"--fork\b", fill_params):
        return None
    m = re.search(r"--until[=\s]+(\S+)", fill_params)
    return m.group(1) if m else None


def applicable_ranges(fork_ranges: list[dict], until_fork: str) -> list[dict]:
    """
    Return fork ranges whose ``from`` is at or before *until_fork*.

    Clamp the last applicable range's ``until`` to *until_fork* so we
    never generate beyond the feature's declared boundary.
    """
    limit = FORK_INDEX[until_fork]
    result = []
    for r in fork_ranges:
        if FORK_INDEX[r["from"]] <= limit:
            entry = dict(r)
            if FORK_INDEX[r["until"]] > limit:
                entry["until"] = until_fork
            result.append(entry)
    return result


def pre_alloc_entries(
    feature: dict, name: str, fork_ranges: list[dict]
) -> list[dict]:
    """
    Build phase-1 matrix entries.

    ``--fork=X`` features emit a single entry with empty
    ``from_fork``/``until_fork`` — the feature's own ``--fork`` flag
    already scopes fill, and passing ``--from``/``--until`` alongside
    ``--fork`` is rejected by fill.

    ``--until=X`` features emit one entry per applicable fork range.
    """
    fork_arg = parse_fork_arg(feature["fill-params"])
    if fork_arg:
        return [
            {
                "feature": name,
                "label": fork_arg.lower(),
                "from_fork": "",
                "until_fork": "",
            }
        ]

    until = parse_until_fork(feature["fill-params"])
    if not until or not fork_ranges:
        return []

    return [
        {
            "feature": name,
            "label": r["label"],
            "from_fork": r["from"],
            "until_fork": r["until"],
        }
        for r in applicable_ranges(fork_ranges, until)
    ]


def legacy_build_entries(
    feature: dict, name: str, fork_ranges: list[dict]
) -> list[dict]:
    """
    Build phase-2 entries for the legacy ``splits < 2`` path.

    Returns one entry per applicable fork range for ``--until=X``
    features, or a single unsplit entry otherwise. Every entry carries
    ``splits=1``/``group=1`` so the downstream action can treat split
    and unsplit uniformly.
    """
    until = parse_until_fork(feature["fill-params"])
    if until and fork_ranges:
        ranges = applicable_ranges(fork_ranges, until)
        if len(ranges) > 1:
            return [
                {
                    "feature": name,
                    "label": r["label"],
                    "from_fork": r["from"],
                    "until_fork": r["until"],
                    "splits": 1,
                    "group": 1,
                }
                for r in ranges
            ]

    return [
        {
            "feature": name,
            "label": "",
            "from_fork": "",
            "until_fork": "",
            "splits": 1,
            "group": 1,
        }
    ]


def split_build_entries(feature: dict, name: str) -> list[dict]:
    """
    Build phase-2 entries for the ``splits >= 2`` path.

    One entry per pytest-split group. No fork-range axis: the plugin
    balances ``(function, fork)`` groups across runners inside a single
    pytest session, so each runner fills the full feature scope with
    ``--grouped-split --splits=N --group=g``.
    """
    splits = int(feature["splits"])
    return [
        {
            "feature": name,
            "label": str(g),
            "from_fork": "",
            "until_fork": "",
            "splits": splits,
            "group": g,
        }
        for g in range(1, splits + 1)
    ]


def build_matrix(
    feature: dict, name: str, fork_ranges: list[dict]
) -> dict[str, object]:
    """
    Build every matrix output for a single feature.

    Returns a dict with ``build_matrix``, ``pre_alloc_matrix``,
    ``combine_labels``, and ``pre_alloc_labels`` keys.
    """
    splits = int(feature.get("splits", 1))

    if splits >= 2:
        pre_alloc = pre_alloc_entries(feature, name, fork_ranges)
        build = split_build_entries(feature, name)
    else:
        pre_alloc = []
        build = legacy_build_entries(feature, name, fork_ranges)

    combine_labels = " ".join(e["label"] for e in build if e["label"])
    pre_alloc_labels = " ".join(e["label"] for e in pre_alloc)

    return {
        "build_matrix": build,
        "pre_alloc_matrix": pre_alloc,
        "combine_labels": combine_labels,
        "pre_alloc_labels": pre_alloc_labels,
    }


def main() -> None:
    """Entry point."""
    if len(sys.argv) != 2:
        print(
            "Usage: generate_build_matrix.py <feature>",
            file=sys.stderr,
        )
        sys.exit(1)

    config = load_config(FEATURE_CONFIG)
    fork_ranges = load_config(FORK_RANGES_CONFIG) or []
    name = sys.argv[1]

    if (
        not isinstance(config, dict)
        or name not in config
        or not isinstance(config[name], dict)
    ):
        print(
            f"Error: feature '{name}' not found in {FEATURE_CONFIG}.",
            file=sys.stderr,
        )
        sys.exit(1)

    assert isinstance(fork_ranges, list)
    result = build_matrix(config[name], name, fork_ranges)

    print(f"build_matrix={json.dumps(result['build_matrix'])}")
    print(f"pre_alloc_matrix={json.dumps(result['pre_alloc_matrix'])}")
    print(f"pre_alloc_labels={result['pre_alloc_labels']}")
    print(f"feature_name={name}")
    print(f"combine_labels={result['combine_labels']}")


if __name__ == "__main__":
    main()
