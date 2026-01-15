"""
Pytest fixtures for the `consume enginex` simulator.

Configures the hive back-end & EL clients for test execution with `BlockchainEngineXFixtures`.
Uses multi-test client architecture to reuse clients across tests with the same pre-alloc group.
"""

import io
import logging
from typing import Generator, Mapping

import pytest
from hive.client import Client, ClientType
from hive.testing import HiveTest, HiveTestResult, HiveTestSuite

from execution_testing.fixtures import BlockchainEngineXFixture
from execution_testing.fixtures.blockchain import FixtureHeader
from execution_testing.fixtures.pre_alloc_groups import PreAllocGroup

from ..helpers.test_tracker import (
    PreAllocGroupTestTracker,
    enginex_group_counts_key,
    format_group_identifier,
)
from ..multi_test_client import MultiTestClientManager
from ..timing_data import TimingData

logger = logging.getLogger(__name__)

pytest_plugins = (
    "execution_testing.cli.pytest_commands.plugins.pytest_hive.pytest_hive",
    "execution_testing.cli.pytest_commands.plugins.consume.simulators.base",
    "execution_testing.cli.pytest_commands.plugins.consume.simulators.multi_test_client",
    "execution_testing.cli.pytest_commands.plugins.consume.simulators.test_case_description",
    "execution_testing.cli.pytest_commands.plugins.consume.simulators.timing_data",
    "execution_testing.cli.pytest_commands.plugins.consume.simulators.exceptions",
    "execution_testing.cli.pytest_commands.plugins.consume.simulators.helpers.test_tracker",
    "execution_testing.cli.pytest_commands.plugins.consume.simulators.engine_api",
)


def pytest_configure(config: pytest.Config) -> None:
    """Set the supported fixture formats for the enginex simulator."""
    config.supported_fixture_formats = [BlockchainEngineXFixture]  # type: ignore[attr-defined]


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    """
    Count tests per pre-allocation group during collection phase.

    This hook analyzes all collected test items to determine how many tests
    belong to each pre-alloc group, enabling automatic client cleanup when
    all tests in a group complete.

    Uses `trylast=True` to run after test deselection (from `-k`, `-m` filters).
    Reads group identifiers from `xdist_group` markers added in
    `pytest_generate_tests`.
    """
    supported_formats = getattr(config, "supported_fixture_formats", [])
    if BlockchainEngineXFixture not in supported_formats:
        return

    group_counts: dict[str, int] = {}

    for item in items:
        # Extract group identifier from xdist_group marker
        # (marker was added in pytest_generate_tests in consume.py)
        group_identifier = None
        for marker in item.iter_markers("xdist_group"):
            if hasattr(marker, "kwargs") and "name" in marker.kwargs:
                group_identifier = marker.kwargs["name"]
                break

        if group_identifier:
            group_counts[group_identifier] = (
                group_counts.get(group_identifier, 0) + 1
            )

    if group_counts:
        # Store counts in session stash for the test tracker fixture to use
        session.stash[enginex_group_counts_key] = group_counts
        logger.info(
            f"Counted {len(group_counts)} pre-alloc groups with "
            f"{sum(group_counts.values())} total tests"
        )

        # Sort tests by group_identifier to ensure consecutive execution
        # This minimizes client thrashing and enables immediate client cleanup
        def get_group_key(item: pytest.Item) -> str:
            """Extract group identifier from item for sorting."""
            for marker in item.iter_markers("xdist_group"):
                if hasattr(marker, "kwargs") and "name" in marker.kwargs:
                    return marker.kwargs["name"]
            raise AssertionError(
                f"EngineX test '{item.nodeid}' missing xdist_group marker"
            )

        items.sort(key=get_group_key)
        logger.info(
            "Sorted tests by pre-alloc group for consecutive execution"
        )
    else:
        logger.warning("No enginex test groups found during collection")


@pytest.fixture(scope="session", autouse=True)
def _configure_client_manager(
    multi_test_client_manager: MultiTestClientManager,
    pre_alloc_group_test_tracker: PreAllocGroupTestTracker,
) -> None:
    """Wire the test tracker to the client manager at session start."""
    multi_test_client_manager.set_test_tracker(pre_alloc_group_test_tracker)


@pytest.fixture(scope="function", autouse=True)
def _ensure_hive_test_reporting(hive_test: HiveTest) -> None:
    """
    Ensure hive_test fixture runs for each test.

    This autouse fixture ensures that hive_test is requested for every test,
    which triggers:
    1. Client startup (via hive_test's dependency on client)
    2. Test registration with hive
    3. Per-test log tracking via register_shared_client
    """
    pass  # hive_test handles everything in its setup/teardown


@pytest.fixture(scope="module")
def test_suite_name() -> str:
    """The name of the hive test suite used in this simulator."""
    return "eels/consume-enginex"


@pytest.fixture(scope="module")
def test_suite_description() -> str:
    """The description of the hive test suite used in this simulator."""
    return (
        "Execute blockchain tests against clients using the Engine API with "
        "pre-allocation group optimization using Engine X fixtures."
    )


@pytest.fixture(scope="function")
def check_live_port(test_suite_name: str) -> int:
    """Port used by hive to check for liveness of the client."""
    return 8551  # Engine API port


@pytest.fixture(scope="function")
def client(
    shared_hive_test: HiveTest,
    multi_test_client_manager: MultiTestClientManager,
    fixture: BlockchainEngineXFixture,
    client_type: ClientType,
    environment: dict,
    client_files: Mapping[str, io.BufferedReader],
    total_timing_data: TimingData,
    request: pytest.FixtureRequest,
) -> Generator[Client, None, None]:
    """
    Get or create a shared client for this test's pre-allocation group.

    This function-scoped fixture is called for each test, but it reuses clients
    across tests that share the same pre-allocation group. Clients are managed
    via `shared_hive_test` for cross-test reuse.

    Note: Per-test registration with hive (for log tracking) is handled by
    the `hive_test` fixture which depends on this fixture.
    """
    group_identifier = fixture.pre_hash
    test_id = request.node.nodeid

    # Check for existing client
    existing_client = multi_test_client_manager.get_client(group_identifier)
    if existing_client is not None:
        logger.info(
            f"♻️  Reusing client for group "
            f"{format_group_identifier(group_identifier)}"
        )
        try:
            yield existing_client
        finally:
            multi_test_client_manager.mark_test_completed(
                group_identifier, test_id
            )
        return

    # Start new client
    logger.info(
        f"🚀 Starting client ({client_type.name}) for group "
        f"{format_group_identifier(group_identifier)}"
    )

    with total_timing_data.time("Start client"):
        client = shared_hive_test.start_client(
            client_type=client_type,
            environment=environment,
            files=client_files,
        )

    assert client is not None, (
        f"Unable to connect to client ({client_type.name}) via Hive. "
        "Check the client or Hive server logs for more information."
    )

    # Mark client as shared for register_shared_client to work.
    # This enables per-test log tracking via the registerSharedNode API.
    client.shared = True

    logger.info(
        f"Client ({client_type.name}) ready for group "
        f"{format_group_identifier(group_identifier)}"
    )

    multi_test_client_manager.register_client(group_identifier, client)

    try:
        yield client
    finally:
        multi_test_client_manager.mark_test_completed(
            group_identifier, test_id
        )


@pytest.fixture(scope="function")
def genesis_header(pre_alloc_group: PreAllocGroup) -> FixtureHeader:
    """Provide the genesis header from the pre-allocation group."""
    return pre_alloc_group.genesis


@pytest.fixture(scope="function")
def hive_test(
    request: pytest.FixtureRequest,
    test_suite: HiveTestSuite,
    client: Client,
) -> Generator[HiveTest, None, None]:
    """
    Override base hive_test to ensure client starts BEFORE test timing begins.

    By depending on `client`, client startup occurs during fixture setup,
    before `test_suite.start_test()` begins the test timer. This ensures:
    1. Client startup time is NOT attributed to the first test in a group.
    2. Each test gets its own `clientInfo` via `register_shared_client`.
    """
    try:
        test_case_description = request.getfixturevalue("test_case_description")
    except pytest.FixtureLookupError:
        pytest.exit(
            "Error: The 'test_case_description' fixture has not been defined!"
        )

    test_parameter_string = request.node.name
    test: HiveTest = test_suite.start_test(
        name=test_parameter_string,
        description=test_case_description,
    )

    # Register the shared client with this test for individual log tracking.
    test.register_shared_client(client)

    yield test

    try:
        # Collect all logs from all phases.
        captured = []
        setup_out = ""
        call_out = ""
        for phase in ("setup", "call", "teardown"):
            report = getattr(request.node, f"result_{phase}", None)
            if report:
                stdout = report.capstdout or "None"
                stderr = report.capstderr or "None"

                # Remove setup output from call phase output.
                if phase == "setup":
                    setup_out = stdout
                if phase == "call":
                    call_out = stdout
                    if call_out.startswith(setup_out):
                        stdout = call_out.removeprefix(setup_out)

                captured.append(
                    f"# Captured Output from Test {phase.capitalize()}\n\n"
                    f"## stdout:\n{stdout}\n"
                    f"## stderr:\n{stderr}\n"
                )

        captured_output = "\n".join(captured)

        if (
            hasattr(request.node, "result_call")
            and request.node.result_call.passed
        ):
            test_passed = True
            test_result_details = "Test passed.\n\n" + captured_output
        elif (
            hasattr(request.node, "result_call")
            and not request.node.result_call.passed
        ):
            test_passed = False
            test_result_details = (
                request.node.result_call.longreprtext + "\n" + captured_output
            )
        elif (
            hasattr(request.node, "result_setup")
            and not request.node.result_setup.passed
        ):
            test_passed = False
            test_result_details = (
                "Test setup failed.\n\n"
                + request.node.result_setup.longreprtext
                + "\n"
                + captured_output
            )
        elif (
            hasattr(request.node, "result_teardown")
            and not request.node.result_teardown.passed
        ):
            test_passed = False
            test_result_details = (
                "Test teardown failed.\n\n"
                + request.node.result_teardown.longreprtext
                + "\n"
                + captured_output
            )
        else:
            test_passed = False
            test_result_details = (
                "Test failed for unknown reason (setup or call status unknown).\n\n"
                + captured_output
            )

        test.end(
            result=HiveTestResult(
                test_pass=test_passed, details=test_result_details
            )
        )
        logger.info(f"Finished processing logs for test: {request.node.nodeid}")

    except Exception as e:
        logger.warning(
            f"Error processing logs for test {request.node.nodeid}: {str(e)}"
        )
        test_passed = False
        test_result_details = (
            f"Exception whilst processing test result: {str(e)}"
        )
        test.end(
            result=HiveTestResult(
                test_pass=test_passed, details=test_result_details
            )
        )
