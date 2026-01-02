# Grammar Check Task

Process ONE unchecked item from `repo_subpaths_for_grammar_check.md` and create a PR to `fix-grammar-docs-and-misc`.

## CRITICAL RULES

- **Branch**: `fix-grammar-docs-and-misc` (NOT `fix-grammar`, `main`, or `forks/amsterdam`)
- **Linting**: `uvx ruff` (NOT `uv run ruff`)
- **PR**: Provide link (NO `gh` CLI - unavailable)
- **Commits**: ONE commit per PR (use `--amend` for changes)

## Step 1: Setup

```bash
git fetch origin fix-grammar-docs-and-misc && git checkout fix-grammar-docs-and-misc && git pull origin fix-grammar-docs-and-misc
git rebase fix-grammar-docs-and-misc  # ensure your branch is based on it
```

If `ls grammar_check_prompt.md` fails, rebase again. **Stay on this branch - do NOT switch.**

## Step 2: Find Task

Read `repo_subpaths_for_grammar_check.md`. Find the FIRST `[ ]` item.

## Step 3: Process Files (MAIN TASK)

**READ EVERY FILE COMPLETELY. Check every sentence. Do not rush.**

Use Glob to find all matching files. For each file:

- **`.py`**: Check docstrings, `#` comments, and string messages only
- **`.md`**: Check ALL prose, skip code blocks

### REQUIRED: Per-File Output

For EVERY file, output this (even if no errors):

```text
FILE: path/to/file.md
ERRORS: 0 | or list each error with line number
```

Example with errors:

```text
FILE: docs/running_tests/cache.md
ERRORS: 2
- Line 15: "refer the" → "refer to the"
- Line 42: "the the" → "the"
```

**Do NOT skip this output. It ensures you checked each file.**

### What to Fix (HIGH confidence)

1. Missing prepositions ("refer the" → "refer to the")
2. Subject-verb disagreement
3. Missing articles
4. Double words ("the the")
5. Clear typos

### What to Flag (LOW confidence → append to `grammar_manual_verification.md`)

```markdown
- [ ] path/to/file.md:15 - "original text"
  Suggestion: "corrected text"
  Reason: brief explanation
```

### What NOT to Fix

- Variable/function/class names or any code logic
- Technical terms (keccak, modexp, precompile)
- Abbreviated references ("the tx", "the msg")
- Content inside code blocks, URLs, file paths
- Capitalization unless clearly wrong
- Docstring style - match neighbors (if they use "Adds", use "Multiplies" not "Multiply")

## Step 4: Lint & Commit

Mark item `[x]` in `repo_subpaths_for_grammar_check.md`.

**Python**: 79 char max for docstrings/comments, then: `uvx ruff format && uvx ruff check --fix`

**Markdown**: Blank lines around code blocks and headings, no trailing spaces.

```bash
git add -A && git commit -m "docs: fix grammar in {subpath}"
```

If making additional changes, amend: `git commit --amend -m "updated message"`

## Step 5: Push & PR

```bash
git fetch origin fix-grammar-docs-and-misc && git rebase origin/fix-grammar-docs-and-misc
git push -u origin HEAD
```

Provide (as clickable link, not code block):

https://github.com/danceratopz/execution-specs/compare/fix-grammar-docs-and-misc...{your-branch-name}?expand=1

PR title: `docs: fix grammar in {subpath}`

## Summary

End with: "Fixed N issues in M files. Flagged K for manual review."

**THOROUGHNESS IS PRIORITY #1** - Missing errors is worse than slow operational steps.
