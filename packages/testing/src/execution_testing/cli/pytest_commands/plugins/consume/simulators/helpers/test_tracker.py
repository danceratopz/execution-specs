"""Test completion tracking for multi-test client architectures."""

import logging
from typing import Dict, Set

import pytest
from pytest import StashKey

logger = logging.getLogger(__name__)

# Typed stash keys for session-scoped data (replaces dynamic attributes)
enginex_group_counts_key: StashKey[Dict[str, int]] = StashKey()


def format_group_identifier(group_identifier: str, max_len: int = 16) -> str:
    """
    Safely format group identifier for logging.

    Args:
        group_identifier: Group identifier string (e.g., pre_hash)
        max_len: Maximum length for formatted output

    Returns:
        Formatted string, truncated if necessary
    """
    if len(group_identifier) <= max_len:
        return group_identifier
    return group_identifier[:max_len]


class PreAllocGroupTestTracker:
    """
    Tracks test completion per pre-allocation group to enable automatic client cleanup.

    This tracker maintains counts of expected vs. completed tests for each group.
    When all tests in a group complete, it signals that the associated client can be stopped.
    """

    def __init__(self) -> None:
        """Initialize the test tracker."""
        self.expected_counts: Dict[
            str, int
        ] = {}  # group_identifier -> total expected tests
        self.completed_tests: Dict[
            str, Set[str]
        ] = {}  # group_identifier -> set of completed test IDs
        logger.info("PreAllocGroupTestTracker initialized")

    def set_group_test_count(self, group_identifier: str, count: int) -> None:
        """
        Set the expected number of tests for a group.

        This is typically called during pytest collection phase.

        Args:
            group_identifier: The group identifier
            count: Expected number of tests in this group
        """
        self.expected_counts[group_identifier] = count
        self.completed_tests[group_identifier] = set()
        logger.debug(
            f"Set expected test count for group {format_group_identifier(group_identifier)}: {count}"
        )

    def mark_test_completed(self, group_identifier: str, test_id: str) -> bool:
        """
        Mark a test as completed and check if the group is now complete.

        Args:
            group_identifier: The group identifier
            test_id: Unique identifier for the test

        Returns:
            True if all tests in the group are now complete, False otherwise
        """
        if group_identifier not in self.completed_tests:
            logger.warning(
                f"Marking test complete for unknown group {format_group_identifier(group_identifier)}, initializing"
            )
            self.completed_tests[group_identifier] = set()

        self.completed_tests[group_identifier].add(test_id)
        completed = len(self.completed_tests[group_identifier])
        expected = self.expected_counts.get(group_identifier, 0)

        logger.debug(
            f"Group {format_group_identifier(group_identifier)}: {completed}/{expected} tests completed"
        )

        # Check if group is complete
        is_complete = completed >= expected and expected > 0
        if is_complete:
            logger.info(
                f"✓ Pre-alloc group {format_group_identifier(group_identifier)} complete "
                f"({completed}/{expected} tests)"
            )

        return is_complete


@pytest.fixture(scope="session")
def pre_alloc_group_test_tracker(
    request: pytest.FixtureRequest,
) -> PreAllocGroupTestTracker:
    """
    Provide session-scoped test tracker for automatic client cleanup.

    This fixture initializes the tracker and populates it with test counts
    from the collection phase (if available via pytest stash).
    """
    tracker = PreAllocGroupTestTracker()

    # Load test counts from session stash (set during collection)
    session = request.session
    group_counts = session.stash.get(enginex_group_counts_key, None)
    if group_counts is not None:
        for group_identifier, count in group_counts.items():
            tracker.set_group_test_count(group_identifier, count)
        logger.info(
            f"Loaded {len(group_counts)} group counts from session stash"
        )

    return tracker
