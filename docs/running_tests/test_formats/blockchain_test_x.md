# Blockchain X Tests  <!-- markdownlint-disable MD051 (MD051=link-fragments "Link fragments should be valid") -->

The Blockchain X Test fixture format tests are included in the fixtures subdirectory `blockchain_tests_x`. They carry RLP-encoded blocks, like [Blockchain Tests](./blockchain_test.md), built on top of the genesis of a shared pre-allocation group, like [Blockchain Engine X Tests](./blockchain_test_engine_x.md).

These are produced by the `StateTest` and `BlockchainTest` test specs for the forks before Paris when filling with the `--generate-all-formats` flag, or with the `--generate-pre-alloc-groups` and `--use-pre-alloc-groups` flags.

## Description

A Blockchain X test is a [Blockchain Test](./blockchain_test.md) whose genesis is not its own. Tests are grouped by their initial state (fork, genesis environment and pre-allocation), and every test of a group starts from the group's genesis. A consumer can therefore start one client per group and run every test of the group against it, instead of starting a client per test.

The fixture keeps the blocks of a Blockchain Test unchanged: the RLP of each block (header, transactions and uncles), and for an invalid block the exception it is expected to raise. It drops the fields that describe the test's own genesis state, `pre` and `postState`, and adds the two fields Blockchain Engine X uses instead: [`preHash`](#-prehash-string), which names the pre-allocation group, and [`postStateDiff`](#-poststatediff-alloc), the accounts the test changed.

A single JSON fixture file is composed of a JSON object where each key-value pair is a different [`BlockchainTestXFixture`](#blockchaintestxfixture) test object, with the key string representing the test name.

The JSON file path plus the test name are used as the unique test identifier.

## Relation to Other Formats

| Format | Blocks as | Genesis | Grouped |
| --- | --- | --- | --- |
| [`blockchain_test`](./blockchain_test.md) | RLP | the test's own | no |
| `blockchain_test_x` | RLP | the group's | yes |
| [`blockchain_test_engine`](./blockchain_test_engine.md) | Engine API payloads | the test's own | no |
| [`blockchain_test_engine_x`](./blockchain_test_engine_x.md) | Engine API payloads | the group's | yes |

`blockchain_test_x` is to `blockchain_test` what `blockchain_test_engine_x` is to `blockchain_test_engine`. Its blocks are meant to execute like the blocks of the test's `blockchain_test` fixture, and a fill checks that they do (see [Usage Notes](#usage-notes)). Only values derived from the genesis differ: each block's `stateRoot`, `parentHash` and `hash`, the same fields of its uncle headers and the `uncleHash` of a block with uncles, the block's `rlp`, which encodes them, and before Byzantium each receipt's `postState` (an intermediate state root) and the `receiptTrie` that commits to it.

Blocks before the merge exist only as RLP: an Engine API payload has no difficulty, nonce or uncles. So `blockchain_test_x` is the grouped format that covers the forks before Paris, which `blockchain_test_engine_x` cannot represent.

## Pre-Allocation Groups

`blockchain_test_x` writes its pre-allocation groups beside those of `blockchain_test_engine_x`, in the `pre_alloc` directory under `blockchain_tests_engine_x`. A group is keyed on the fork, the genesis environment and the pre-allocation of its tests (plus a salt for tests that ask for their own group). It lists each test once, by the test ID of its grouped fixture, which names the format (for example `test.py::test_name[fork_London-blockchain_test_x]`). Each fork has one grouped format, so a group holds the tests of one format only.

See [Pre-Allocation Groups Folder](./blockchain_test_engine_x.md#pre-allocation-groups-folder) for the structure of a group file. The `pre_alloc` directory must be distributed with the fixtures, also when a fill only produced `blockchain_test_x` fixtures (for example a fill of forks before Paris only).

## Fork Support

The format is filled for the forks before Paris only. From Paris on, [`blockchain_test_engine_x`](./blockchain_test_engine_x.md) covers the pre-allocation groups, so every fork has exactly one grouped format, and a release that contains both covers every fork.

## Consumption

For each [`BlockchainTestXFixture`](#blockchaintestxfixture) test object in the JSON fixture file:

1. Load the pre-allocation group: read the file named [`preHash`](#-prehash-string) from `blockchain_tests_engine_x/pre_alloc`, and take its `pre` allocation and its `genesis` header.
2. Start a client for the group (or reuse the group's client): use [`network`](#-network-fork) for the fork schedule, the group's `pre` as the starting state, and the group's `genesis` as the genesis header. [`genesisBlockHeader`](#-genesisblockheader-fixtureheader) equals the group's genesis.
3. Deliver the [`blocks`](#-blocks-listfixtureblockinvalidfixtureblock) in order, as for a [Blockchain Test](./blockchain_test.md#consumption): each valid block must be imported, and each invalid block must be rejected with its expected exception.
4. Compare the final chain head against [`lastblockhash`](#-lastblockhash-hash).
5. Verify the final state: apply [`postStateDiff`](#-poststatediff-alloc) to the group's `pre` and compare the result with the client's state.

Every test of a group is an independent chain that forks at the group's genesis, so a client reused across the group must be able to switch to the head of each test in turn.

[`consume wirex`](../consume/wirex.md) reads this format: it reuses one client per pre-allocation group and makes the client sync each test's blocks from a mock devp2p peer. It names each test's last block by hash in a forkchoice update (see [Pre-Merge Forks](../consume/wirex.md#pre-merge-forks)).

## Structures

### `BlockchainTestXFixture`

#### - `network`: [`Fork`](./common_types.md#fork)

##### TO BE DEPRECATED

Fork configuration for the test.

This field is going to be replaced by the value contained in `config.network`.

#### - `preHash`: `string`

Hash identifier referencing a pre-allocation group in the `blockchain_tests_engine_x/pre_alloc` folder. It is `0x`-prefixed, 8 bytes wide, and matches both the group file's name and its `groupHash` field.

#### - `genesisBlockHeader`: [`FixtureHeader`](./blockchain_test.md#fixtureheader)

Genesis block header of the pre-allocation group, the parent of the first block.

#### - `genesisRLP`: [`Bytes`](./common_types.md#bytes)

RLP serialization of the genesis block.

#### - `blocks`: [`List`](./common_types.md#list)`[`[`FixtureBlock`](./blockchain_test.md#fixtureblock)` | `[`InvalidFixtureBlock`](./blockchain_test.md#invalidfixtureblock)`]`

List of blocks to be processed after the genesis block, in the same structures as in a [Blockchain Test](./blockchain_test.md#fixtureblock).

#### - `lastblockhash`: [`Hash`](./common_types.md#hash)

Hash of the last valid block, or the genesis block hash if all blocks are invalid.

#### - `postStateHash`: [`Optional`](./common_types.md#optional)`[`[`Hash`](./common_types.md#hash)`]`

State root after the last valid block. Present for tests that do not output a full post state.

#### - `postStateDiff`: [`Alloc`](./common_types.md#alloc-mappingaddressaccount)

State differences from the pre-allocation group after test execution: the accounts that changed, were created (present here but not in the group) or were deleted (`null`). See [`postStateDiff`](./blockchain_test_engine_x.md#-poststatediff-alloc) in Blockchain Engine X Tests for how to reconstruct the final state.

#### - `sealEngine`: `str`

Deprecated: Seal engine to use for the test. Always `NoProof`.

#### - `config`: [`FixtureConfig`](./blockchain_test.md#fixtureconfig)

Chain configuration object to be applied to the client running the test.

## Usage Notes

- The format is generated only in the two pre-allocation phases: with `--generate-all-formats`, or with `--generate-pre-alloc-groups` followed by `--use-pre-alloc-groups`. A plain `fill` does not produce it.
- Its fixtures never share transition tool outputs with other formats: they execute against the group's genesis.
- After a fill, the blocks of every fixture are compared with the test's `blockchain_test` fixture, field by field apart from the genesis-derived ones. When that fixture has a full post state, the group's `pre` with [`postStateDiff`](#-poststatediff-alloc) applied must also equal it on the test's accounts, and every account the diff names must appear in it as the diff has it. Any difference fails the fill. This catches an account that group packing leaked into a test when the leak changes a block or, for a test with a full post state, the test's post state, as the same check of `blockchain_test_engine_x` fixtures does from Paris on.
- `blockchain_test_only` keeps the format (it is an RLP format); `blockchain_test_engine_only` discards it.
