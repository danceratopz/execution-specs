"""
Utilities for pytest-split ``.test_durations`` files.

``--store-durations`` records nodeids with the ``@xdist_group`` suffix
appended during execution (e.g. ``@t8n-cache-<hash>``), but pytest
collection sees bare nodeids. These helpers bridge the two so the
plugin and the CI scripts share one implementation of suffix
stripping, normalization, and per-group merging.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def strip_xdist_suffix(nodeid: str) -> str:
    """Strip the ``@xdist_group`` suffix from a pytest nodeid."""
    return nodeid.split("@", 1)[0]


def normalize_durations(raw: dict[str, float]) -> dict[str, float]:
    """
    Return *raw* with ``@xdist_group`` suffixes removed from every key.

    When two keys collapse to the same stripped form (e.g. runs with
    different t8n-cache ids), the last one wins.
    """
    return {strip_xdist_suffix(k): v for k, v in raw.items()}


def merge_durations(
    sources: Iterable[dict[str, float]],
) -> dict[str, float]:
    """
    Flat-merge *sources* into a single durations dict.

    Fork-range and pytest-split groups produce disjoint nodeid sets by
    construction, so collisions are expected to be empty; if any occur,
    the last source wins.
    """
    merged: dict[str, float] = {}
    for src in sources:
        merged.update(src)
    return merged


def load_durations(path: Path) -> dict[str, float]:
    """Read a ``.test_durations`` JSON file; empty dict if absent."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def write_durations(path: Path, data: dict[str, float]) -> None:
    """Serialize *data* as JSON to *path*, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
