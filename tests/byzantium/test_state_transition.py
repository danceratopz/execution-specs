from functools import partial

import pytest

from ethereum.utils.ensure import EnsureError
from tests.byzantium.blockchain_st_test_helpers import (
    FIXTURES_LOADER,
    run_byzantium_blockchain_st_tests,
)
from tests.helpers.load_state_tests import fetch_state_test_files

# Run legacy general state tests
test_dir = (
    "tests/fixtures/LegacyTests/Constantinople/BlockchainTests/"
    "GeneralStateTests/"
)

run_general_state_tests = partial(run_byzantium_blockchain_st_tests, test_dir)

# Every test below takes more than  60s to run and
# hence they've been marked as slow
SLOW_TESTS = (
    # TODO: Remove the file names in the list below.
    # These tests are currently failing because some precompiles are not
    # implemented. Marking them as slow for now so that these failing tests
    # get skipped.
    "stPreCompiledContracts/sec80_d0g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_noncestorage_d1g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_noncestorage_d0g0v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d15g1v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d14g1v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d21g1v0.json",
    "stRevertTest/RevertPrecompiledTouch_d3g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_d2g0v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d31g1v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d30g1v0.json",
    "stRevertTest/RevertPrecompiledTouch_storage_d3g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_storage_d2g0v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d5g1v0.json",
    "stRevertTest/RevertPrecompiledTouch_nonce_d2g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_nonce_d3g0v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d13g1v0.json",
    "stRevertTest/RevertInCreateInInit_d0g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_d0g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_d1g0v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d22g1v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d23g1v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d29g1v0.json",
    "stRevertTest/RevertPrecompiledTouch_noncestorage_d2g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_noncestorage_d3g0v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d7g1v0.json",
    "stRevertTest/RevertPrecompiledTouchExactOOG_d6g1v0.json",
    "stRevertTest/RevertPrecompiledTouch_nonce_d1g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_nonce_d0g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_storage_d0g0v0.json",
    "stRevertTest/RevertPrecompiledTouch_storage_d1g0v0.json",
    "stRandom2/randomStatetest642_d0g0v0.json",
    "stStaticCall/static_CallEcrecover0_0input_d8g0v0.json",
    "stStaticCall/static_CallEcrecover0_0input_d7g0v0.json",
    "stStaticCall/static_CallEcrecover0_0input_d6g0v0.json",
)


@pytest.mark.parametrize(
    "test_file", fetch_state_test_files(test_dir, SLOW_TESTS, FIXTURES_LOADER)
)
def test_general_state_tests(test_file: str) -> None:
    try:
        run_general_state_tests(test_file)
    except KeyError:
        # FIXME: Handle tests that don't have post state
        pytest.xfail(f"{test_file} doesn't have post state")


# Run legacy valid block tests
test_dir = (
    "tests/fixtures/LegacyTests/Constantinople/BlockchainTests/ValidBlocks/"
)

run_valid_block_test = partial(
    run_byzantium_blockchain_st_tests,
    test_dir,
)


@pytest.mark.parametrize(
    "test_file_uncle_correctness",
    [
        "bcUncleTest/oneUncle.json",
        "bcUncleTest/oneUncleGeneration2.json",
        "bcUncleTest/oneUncleGeneration3.json",
        "bcUncleTest/oneUncleGeneration4.json",
        "bcUncleTest/oneUncleGeneration5.json",
        "bcUncleTest/oneUncleGeneration6.json",
        "bcUncleTest/twoUncle.json",
    ],
)
def test_uncles_correctness(test_file_uncle_correctness: str) -> None:
    run_valid_block_test(test_file_uncle_correctness)


# Run legacy invalid block tests
test_dir = (
    "tests/fixtures/LegacyTests/Constantinople/BlockchainTests/InvalidBlocks"
)

run_invalid_block_test = partial(
    run_byzantium_blockchain_st_tests,
    test_dir,
)


@pytest.mark.parametrize(
    "test_file", fetch_state_test_files(test_dir, (), FIXTURES_LOADER)
)
def test_invalid_block_tests(test_file: str) -> None:
    try:
        # Ideally correct.json should not have been in the InvalidBlocks folder
        if test_file == "bcUncleHeaderValidity/correct.json":
            run_invalid_block_test(test_file)
        else:
            with pytest.raises((EnsureError, AssertionError, ValueError)):
                run_invalid_block_test(test_file)
    except KeyError:
        # FIXME: Handle tests that don't have post state
        pytest.xfail(f"{test_file} doesn't have post state")


# Run Non-Legacy GeneralStateTests
run_general_state_tests_new = partial(
    run_byzantium_blockchain_st_tests,
    "tests/fixtures/BlockchainTests/GeneralStateTests/",
)


@pytest.mark.parametrize(
    "test_file_new",
    [
        "stCreateTest/CREATE_HighNonce.json",
        "stCreateTest/CREATE_HighNonceMinus1.json",
    ],
)
def test_general_state_tests_new(test_file_new: str) -> None:
    try:
        run_general_state_tests_new(test_file_new)
    except KeyError:
        # KeyError is raised when a test_file has no tests for frontier
        raise pytest.skip(f"{test_file_new} has no tests for frontier")
