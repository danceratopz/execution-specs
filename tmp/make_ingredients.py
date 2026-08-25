"""
Produce PR #2511 'ingredient' files from filled fixtures.

Thin driver around the PR's own generate_hive_files(): for every
*.json fixture (or pre-alloc group file) in INPUT_DIR, write a
{name}.json to OUTPUT_DIR containing:

    {"genesis": {...generic genesis...}, "environment": {"HIVE_*": ...}}

Run from the repo root with: uv run python tmp/make_ingredients.py
"""

import sys
from pathlib import Path

from execution_testing.fixtures.hive import generate_hive_files

input_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "tmp/input")
output_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "tmp/ingredients")

count = generate_hive_files(input_dir, output_dir)
print(f"wrote {count} ingredient file(s) to {output_dir}")
