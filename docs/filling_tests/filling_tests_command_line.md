# Filling Tests at a Prompt

The execution-testing framework uses the [pytest framework](https://docs.pytest.org/en/latest/) for test case collection and execution. The `fill` command is essentially an alias for `pytest`, which uses several [custom pytest plugins](../library/pytest_plugins/index.md) to run transition tools against test cases and generate JSON fixtures.

!!! note "Options specific to execution-testing"
    The command-line options specific to filling tests can be listed via:

    ```console
    uv run fill --help
    ```

    See [Custom `fill` Command-Line Options](#custom-fill-command-line-options) for all options.

## Collection - Test Exploration

The test cases implemented in the `./tests` sub-directory can be listed in the console using:

```console
uv run fill --collect-only
```

and can be filtered (by test path, function and parameter substring):

```console
uv run fill --collect-only -k warm_coinbase
```

Docstrings are additionally displayed when ran verbosely:

```console
uv run fill --collect-only -k warm_coinbase -vv
```

## Execution

By default, test cases are filled for all forks already deployed to mainnet, but not for forks still under active development, i.e., as of time of writing, Q2 2023:

```console
uv run fill
```

will generate fixtures for test cases from Frontier to Shanghai.

To generate all the test fixtures defined in the `./tests/shanghai` sub-directory and write them to the `./fixtures-shanghai` directory, run `fill` in the top-level directory as:

```console
uv run fill ./tests/shanghai --output="fixtures-shanghai"
```

!!! note "Test case verification"
    Note, that the (limited set of) test `post` conditions are tested against the output of the `evm t8n` command during test generation.

To generate all the test fixtures in the `tests/shanghai/eip3651_warm_coinbase/test_warm_coinbase.py` module, for example, run:

```console
uv run fill tests/shanghai/eip3651_warm_coinbase/test_warm_coinbase.py
```

To generate specific test fixtures from a specific test function or even test function and parameter set, obtain the corresponding test ID using:

```console
uv run fill --collect-only -q -k test_warm_coinbase
```

This filters the tests by `test_warm_coinbase`. Then find the relevant test ID in the console output and provide it to fill, for example, for a test function:

```console
uv run fill tests/shanghai/eip3651_warm_coinbase/test_warm_coinbase.py::test_warm_coinbase_gas_usage
```

or, for a test function and specific parameter combination:

```console
uv run fill tests/shanghai/eip3651_warm_coinbase/test_warm_coinbase.py::test_warm_coinbase_gas_usage[fork_Paris-DELEGATECALL]
```

## Execution for Development Forks

!!! note ""
    By default, test cases are not filled for upcoming Ethereum forks so that they can be readily filled using the `evm` tool from the latest `geth` release.

    In order to fill test cases for an upcoming fork, ensure that the `evm` tool used supports that fork and features under test and use the `--until` or `--fork` flag.

    For example, as of Q2 2023, the current fork under active development is `Cancun`:
    ```console
    uv run fill --until Cancun
    ```

    See: [Filling Tests for Features under Development](./filling_tests_dev_fork.md).

## Generating All Fixture Formats

The `--generate-all-formats` flag enables generation of all fixture formats including the optimized `BlockchainEngineXFixture` in a single command:

```console
uv run fill --generate-all-formats tests/shanghai/
```

This flag automatically performs a two-phase execution:

1. **Phase 1**: Generates pre-allocation groups for optimization.
2. **Phase 2**: Generates all supported fixture formats (`StateFixture`, `BlockchainFixture`, `BlockchainEngineFixture`, `BlockchainEngineXFixture`, etc.).

!!! note "Tarball output requires explicit opt-in"
    Tarball output (`.tar.gz` files) does **not** imply `--generate-all-formats`. Pass the flag explicitly to include the pre-allocation group formats:
    ```console
    uv run fill --generate-all-formats --output=fixtures.tar.gz tests/shanghai/
    ```

## Prepending an Empty Block

By default the filler inserts one empty block between genesis and every blockchain test's first block **in `blockchain_test_engine_x` fixtures only**, so that each engine_x chain is at least two blocks long; every other fixture format's chains are exactly what the test defines. `--no-prepend-empty-block` disables it:

```console
uv run fill --no-prepend-empty-block --generate-all-formats tests/cancun/
```

A consumer that makes the client download and execute a test's own blocks over devp2p needs the client to actually sync, and a client only starts a sync when the announced head's parent is unknown to it. A single-block chain is built directly on the client's own genesis, so its head executes immediately over the Engine API and no sync happens at all. ([`consume sync`](../running_tests/running.md#sync) does not need the extra block: its fixture format carries a sync-trigger block of its own, built on top of the test's last block.)

The prepended block is a real block, built through the same machinery as every other block, and carries a per-test digest in its `extra_data` so that tests sharing a pre-allocation group do not share it. In the fixture, its payload is tagged with the `sync` phase (`"phase": "sync"` on the first `engineNewPayloads` entry), so consumers can tell the framework-injected payload from the test's own; consumers that replay payloads through the Engine API can treat it like any other block. Genesis fee fields are wound one progression step up to cancel the step the extra block introduces, so the test's own blocks execute in the fee environment their author specified. Timestamps are never shifted: a test pinning a timestamp the prepended block cannot clear fails the fill instead of producing a non-monotonic chain.

!!! note "Only engine_x fixtures are affected"
    Prepending shifts every block number and hash, so engine_x fixtures filled with and without it are not comparable. The other blockchain formats never carry the extra block: they share a positional `t8n` output cache and must build byte-identical chains, while engine_x fixtures opt out of that cache and pay no extra `t8n` work for the divergence.

Spec types the extra block would distort opt out and are filled without it (benchmark tests), so a combined fill needs no extra options. Tests that cannot survive the transformation are marked in the tree and fill without the extra block instead of being skipped - no test leaves the fixture release; sync-based consumers skip chains too short to sync at consume time. See [`absolute_block_position`](../writing_tests/test_markers.md#pytestmarkabsolute_block_position) and its sibling markers.

## Debugging the `t8n` Command

The `--evm-dump-dir` flag can be used to dump the inputs and outputs of every call made to the `t8n` command for debugging purposes, see [Debugging Transition Tools](./debugging_t8n_tools.md).

## Watch Mode for Development

!!! tip "Development workflow"
    Use `--watch` or `--watcherfall` during test development to get immediate feedback on your changes without manually re-running the fill command.

### Standard Watch Mode (`--watch`)

This will:

1. Run the initial fill command.
2. Monitor all Python files in the `tests/` and `src/` directories for changes.
3. Automatically re-run the fill command when changes are detected.
4. Clear the screen and show which files changed.

```console
uv run fill tests/amsterdam/eip7928_block_level_access_lists/test_block_access_lists.py --clean --until Amsterdam --watch
✓ Fill completed

Watching for changes...

```

### Watcherfall Watch Mode (`--watcherfall`)

!!! info "Watcherfall mode"
    A verbose mode; like watch but the logs keep flowing - perfect when you want to see the full history of runs without clearing the terminal.

Same as `--watch` but without clearing the terminal between runs, so you can see the full output history:

```console
uv run fill tests/amsterdam/eip7928_block_level_access_lists/test_block_access_lists.py --clean --until Amsterdam --watcherfall
Starting watcherfall mode (verbose)...
✓ Fill completed

Watching for changes...

File changes detected, re-running...

✓ Fill completed

Watching for changes...

```

Exit either watch mode with Ctrl+C

## Other Useful Pytest Command-Line Options

```console
uv run fill -vv            # More verbose output
uv run fill -x             # Exit instantly on first error or failed test case
uv run fill --pdb -nauto   # Drop into the debugger upon error in a test case
uv run fill -s             # Print stdout from tests to the console during execution
```

## Custom `fill` Command-Line Options

To see all the options available to fill, including pytest and pytest plugin options, use `--pytest-help`.

To list the options that only specific to fill, use:

```console
uv run fill --help
```

For a complete, up-to-date list of all command-line options, see the [Fill Command-Line Options](filling_tests_command_line_options.md) page, which is automatically generated from the current `uv run fill --help` output.
