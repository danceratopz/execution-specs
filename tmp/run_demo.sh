#!/usr/bin/env bash
# End-to-end demo of PR #2511 (hive genesis format), both examples.
# Run from the repo root: bash tmp/run_demo.sh [hive_dir]
set -euo pipefail

HIVE=${1:-"$HOME/code/github/hive"}
TMP="$(cd "$(dirname "$0")" && pwd)"

echo "==> Example 1 (PRIMARY, engine-x): fill emits the ingredients itself"
uv run fill --fork Cancun tests/shanghai/eip3855_push0/test_push0.py \
    --generate-all-formats --output "$TMP/fixtures-demo" --clean -q \
    >/dev/null
INGREDIENTS=$(ls "$TMP"/fixtures-demo/blockchain_tests_engine_x/hive/*.json)
echo "    fill wrote: $INGREDIENTS"
bash "$TMP/consume.sh" "$INGREDIENTS" "$HIVE" "$TMP/out/enginex"

echo
echo "==> Example 2 (secondary, standard fixture): standalone producer"
uv run python "$TMP/make_ingredients.py" \
    "$TMP/input/standard" "$TMP/ingredients/standard"
bash "$TMP/consume.sh" "$TMP/ingredients/standard/fixture.json" \
    "$HIVE" "$TMP/out/standard"

echo
echo "==> Done. Client configs under $TMP/out/{enginex,standard}/"
