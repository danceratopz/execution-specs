# PR #2511 end-to-end demo: ingredients → client genesis files

Demonstrates the producer/consumer flow of PR #2511 ("Hive genesis format") using hive's actual mappers from a local hive checkout — no hive runtime, no docker, no EEST dependency on the consumer side.

Run everything: `bash tmp/run_demo.sh` (from the repo root, on branch `feat/hive-genesis`).

## Example 1 (PRIMARY): engine-x fixtures — the case this feature is for

For engine-x, PR #2511 needs **no separate tool at all**: `fill --generate-all-formats` writes the ingredients file itself, one per pre-alloc group, right next to the group file:

```
uv run fill --fork Cancun tests/shanghai/eip3855_push0/test_push0.py \
    --generate-all-formats --output tmp/fixtures-demo --clean
        ▼
tmp/fixtures-demo/blockchain_tests_engine_x/pre_alloc/0xa15e9ec8299de43d.json   (the group)
tmp/fixtures-demo/blockchain_tests_engine_x/hive/0xa15e9ec8299de43d.json        (the ingredients)
        │  bash tmp/consume.sh <ingredients> [hive_dir] tmp/out/enginex
        ▼
tmp/out/enginex/go-ethereum/genesis.json
tmp/out/enginex/besu/genesis.json
tmp/out/enginex/nethermind/genesis.json      (geth-format, post hive#1593 mapper)
tmp/out/enginex/nethermind/config.json       (from mkconfig.jq, env only)
```

The ingredients file is `{"genesis": {...generic genesis...}, "environment": {"HIVE_*": ...}}` — one per pre-alloc group, because the group *is* the genesis: benchmarkoor boots one client per group and runs the group's tests against it. It never needs the member fixtures for this (their pre-state is deduplicated into the group file anyway).

## Example 2 (secondary): standard blockchain fixtures

Plain (non-engine-x) blockchain fixtures are self-contained, so the same flow works per fixture — useful to boot a natively-built client on exactly one failing fixture (debugger attached), instead of a dockerized client inside hive:

```
uv run python tmp/make_ingredients.py tmp/input/standard tmp/ingredients/standard
bash tmp/consume.sh tmp/ingredients/standard/fixture.json <hive_dir> tmp/out/standard
```

`make_ingredients.py` is a 10-line driver around the PR's own `generate_hive_files()`.

## What a consumer needs, in total

1. `jq`
2. hive's `clients/<client>/mapper.jq` files (checked out or vendored, at a pin the consumer chooses)
3. The ~15 lines of `consume.sh`: split the ingredients file, export the `HIVE_*` env, one `jq -f mapper.jq` per client.

Because EEST ships only the chain description, the consumer picks the mapper vintage to match *their* client version — and mapper fixes apply retroactively to already-published releases (re-run one jq; the ingredients never change). This works for every client hive has a mapper for (erigon, reth, ethrex, nimbus included), not just the three modeled by PR #3414.

## Verification vs PR #3414's golden (standard example, go-ethereum)

The consumer output is identical to `extract_config/tests/fixtures/1/cancun/go-ethereum/genesis.json` from PR #3414 after normalizing exactly three deltas:

1. **alloc keys**: hive convention is bare hex (no `0x`), #3414 emits `0x`-prefixed. Nethermind's strict-hex parser requires the `0x` form, so the prefix question is real either way.
2. **blobSchedule**: hive's mapper emits default entries for **all** named forks (prague, osaka, amsterdam, bpo1–bpo5) even on a Cancun-only chain, and geth accepts this in production daily. #3414 does the opposite (`exclude_identical_schedules`), which drops entries geth requires and breaks BPO-target genesis. Hive's behavior is evidence that over-inclusion is safe and under-inclusion is not.
3. **depositContractAddress case**: hive emits the EIP-55 checksummed form; #3414 lowercases it.

## Notes

- PR #2511's March code parsed an August-filled Cancun fixture unchanged (producer side has not bit-rotted); the August *pre-alloc group* format has since evolved, which is why Example 1 fills its own group with the branch's code rather than borrowing a current one.
- Known gap in the PR: `HIVE_CHAIN_ID` is read from the fixture for full fixtures but hardcoded to `1` on the pre-alloc path (the group files carry `chainId` today, so it's a one-line fix).
- `tmp/fixtures-demo/` is generated output — if publishing this demo, commit only `README.md`, `run_demo.sh`, `consume.sh`, `make_ingredients.py`, and `input/`.
