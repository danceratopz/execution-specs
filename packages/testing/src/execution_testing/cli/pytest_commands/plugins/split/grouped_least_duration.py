"""
Greedy least-duration bin-packing for pre-keyed test items.

Given items tagged with a group key (typically the filler plugin's
``xdist_group`` marker), assign each group heaviest-first to the
runner with the smallest running total. Items that share a key stay
on the same runner so any per-group cache they rely on is preserved
across the split.
"""

from __future__ import annotations

import heapq
from collections import OrderedDict
from collections.abc import Sequence
from typing import NamedTuple, Protocol, runtime_checkable

from execution_testing.cli.pytest_commands.plugins.split.durations import (
    strip_xdist_suffix,
)


@runtime_checkable
class _HasNodeId(Protocol):
    """Minimal protocol for items with a ``nodeid`` attribute."""

    @property
    def nodeid(self) -> str:
        """Return the pytest node identifier."""
        ...


class SplitGroup(NamedTuple):
    """One runner's workload after splitting."""

    selected: list[_HasNodeId]
    deselected: list[_HasNodeId]
    duration: float
    max_group_duration: float


def grouped_least_duration(
    splits: int,
    keyed_items: Sequence[tuple[str, _HasNodeId]],
    durations: dict[str, float],
) -> list[SplitGroup]:
    """
    Split *keyed_items* across *splits* runners by group key.

    Each ``(group_key, item)`` pair is routed using *group_key* — items
    sharing a key always land on the same runner. Per-group duration
    is summed from *durations* (keyed by bare nodeid, average for
    unknowns), then groups are assigned heaviest-first to the runner
    with the smallest current total via a min-heap.
    """
    # Build ordered groups, preserving collection order inside each.
    groups: OrderedDict[str, list[_HasNodeId]] = OrderedDict()
    for key, item in keyed_items:
        groups.setdefault(key, []).append(item)

    # Look up each item's duration; fall back to the observed average.
    known: dict[str, float] = {}
    all_items = [item for _, item in keyed_items]
    for item in all_items:
        nid = strip_xdist_suffix(item.nodeid)
        if nid in durations:
            known[nid] = durations[nid]
    avg = sum(known.values()) / len(known) if known else 1.0

    group_durations = {
        key: sum(
            known.get(strip_xdist_suffix(item.nodeid), avg) for item in members
        )
        for key, members in groups.items()
    }

    # Greedy bin-packing: heaviest group -> least-loaded runner.
    sorted_keys = sorted(
        groups, key=lambda k: group_durations[k], reverse=True
    )
    runner_keys: list[list[str]] = [[] for _ in range(splits)]
    runner_totals = [0.0] * splits
    runner_max_group = [0.0] * splits

    heap: list[tuple[float, int]] = [(0.0, i) for i in range(splits)]
    heapq.heapify(heap)
    for key in sorted_keys:
        total, idx = heapq.heappop(heap)
        new_total = total + group_durations[key]
        runner_keys[idx].append(key)
        runner_totals[idx] = new_total
        runner_max_group[idx] = max(
            runner_max_group[idx], group_durations[key]
        )
        heapq.heappush(heap, (new_total, idx))

    # Expand runner -> item lists, preserving collection order within
    # each group so t8n cache hits stay adjacent under ``loadgroup``.
    result: list[SplitGroup] = []
    for i in range(splits):
        selected = [item for key in runner_keys[i] for item in groups[key]]
        selected_ids = {id(item) for item in selected}
        deselected = [
            item for _, item in keyed_items if id(item) not in selected_ids
        ]
        result.append(
            SplitGroup(
                selected=selected,
                deselected=deselected,
                duration=runner_totals[i],
                max_group_duration=runner_max_group[i],
            )
        )
    return result
