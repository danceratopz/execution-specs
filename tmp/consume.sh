#!/usr/bin/env bash
# Consumer side of PR #2511: turn ONE ingredients file plus hive's
# checked-out mapper.jq files into client-native genesis/config files.
# This is everything a consumer (e.g. benchmarkoor) would have to do.
#
# Usage: consume.sh <ingredients.json> [hive_dir] [out_dir]
set -euo pipefail

INGREDIENTS=${1:?usage: consume.sh <ingredients.json> [hive_dir] [out_dir]}
HIVE=${2:-"$HOME/code/github/hive"}
OUT=${3:-"$(cd "$(dirname "$0")" && pwd)/out"}

mkdir -p "$OUT"

# Step 1: split the ingredients file.
jq '.genesis' "$INGREDIENTS" > "$OUT/genesis-input.json"

# Step 2: export the HIVE_* environment the mappers read via env.HIVE_*.
while IFS='=' read -r k v; do
    export "$k"="$v"
done < <(jq -r '.environment | to_entries[] | "\(.key)=\(.value)"' "$INGREDIENTS")

# Step 3: one jq call per client — the entire "transform".
for client in go-ethereum besu nethermind; do
    mkdir -p "$OUT/$client"
    jq -f "$HIVE/clients/$client/mapper.jq" "$OUT/genesis-input.json" \
        > "$OUT/$client/genesis.json"
    echo "wrote $OUT/$client/genesis.json"
done

# Nethermind's node config file is generated from the env alone.
jq -n -f "$HIVE/clients/nethermind/mkconfig.jq" > "$OUT/nethermind/config.json"
echo "wrote $OUT/nethermind/config.json"
