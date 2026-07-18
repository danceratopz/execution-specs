"""
Rewrite shared pinned addresses in `tests/ported_static/` to file-private
ones.

The static-test conversion tooling remapped original filler addresses
with a key derived from the original address only, so hundreds of pinned
addresses are shared across more than one generated file, each with
different content. Any address allocated by more than one pre-alloc
group is reserved bucket-wide during pre-alloc group packing, and every
group's footprint must then agree on it; shared pins with per-file
content therefore make groups unmergeable. This codemod rewrites every
occurrence of a shared pinned address inside each file that pins it to a
deterministic, file-private address, leaving test semantics identical
(same execution, same post state, different addresses).

Safety rules:

- Only addresses pinned via ``deploy_contract(address=...)`` in more
  than one file are targets; file-private pins, ``fund_eoa`` senders,
  and the low/precompile range (<= 0x100) are untouched.
- New addresses are the first 20 bytes of
  ``keccak256(f"{file_relpath}:{original_address:#042x}")``, checked
  against every 40-hex-char sequence anywhere in the tree and against
  other derived addresses.
- Within a file, every occurrence is rewritten consistently: the pin,
  ``Op.*`` operand literals, and raw hex strings (case-insensitive,
  with or without ``0x``, including zero-padded 32-byte words).
- Ambiguity gate: if any occurrence sits inside a longer hex literal
  where it is not clearly the address, the whole (file, address) pair
  is skipped and logged. Clear embedded contexts are pure left
  zero-padding within a 32-byte word, and, inside pure-hex bytecode
  blobs (``bytes.fromhex(...)``/``Bytes(...)`` literals), occurrences
  that a linear EVM disassembly places exactly as a ``PUSH20``
  immediate or as the zero-padded low 20 bytes of a
  ``PUSH21``-``32`` immediate; the conversion tooling itself emits
  remapped addresses into such operands, and a misclassified rewrite
  fails loudly at fill time because ported tests carry full expect
  sections.
- Derivation guard: a candidate is skipped in a file when it is the
  CREATE address of any address literal in that file, or when any
  address literal in that file is one of ITS CREATE addresses
  (collision tests pin accounts at to-be-created addresses on
  purpose). Checked nonces are 0..32 plus any larger nonce literally
  declared in the file; senders declared as ``EOA(key=...)`` are
  resolved to their addresses so their CREATE children are guarded
  too.
- CREATE2 guard: files that use CREATE2 are skipped entirely. A
  CREATE2 result address depends on the creator address and the
  initcode bytes, both of which a remap changes, and unlike CREATE it
  cannot be enumerated statically; such tests hardcode the expected
  result address or pin collision accounts at it, and remapping breaks
  them.
- Run preservation: tests index consecutive pinned addresses
  arithmetically (e.g. ``Op.ADD(0x1000, ...)`` dispatching over
  accounts pinned at 0x1000..0x1004), which couples neighboring
  addresses. Pins within ``RUN_WINDOW`` of each other therefore move
  as a block: the run's lowest address is derived fresh and every
  member (including file-private ones) keeps its offset from the base,
  so intra-run arithmetic stays valid. A guard hit on any member skips
  the whole run. Short integer literals equal to a pinned address are
  rewritten with it; they are polysemous (0x1000 is also a memory
  size), which the loud fill validation and SKIP_FILES fallback
  cover.
- Comments and docstrings are never rewritten (they document original
  filler addresses) and do not trigger the ambiguity gate.
- Fill-failure fallback: files listed in SKIP_FILES keep their
  original addresses entirely. These are tests whose expectations
  encode a transform of a pinned address (a stored bitwise NOT of it,
  a storage-asserted gas measurement that changes with address bytes,
  dynamic code construction), which no textual consistency rewrite can
  follow; they were identified by fill failures and skipping them is
  the intended fallback.

Run from the repository root (relative paths seed the deterministic
address derivation):

    uv run privatize_ported_static_addresses census
    uv run privatize_ported_static_addresses report
    uv run privatize_ported_static_addresses apply

``report`` writes the JSON report and prints a summary without
modifying anything; ``apply`` performs the rewrite, then re-checks that
every touched file still parses and that the only remaining shared pins
are the planned skips; ``census`` prints pin statistics only.

Validation is loud: ported tests carry full expect sections, so any
wrong remap fails at fill time. After applying, fill the tree two-phase
(``fill tests/ported_static --generate-pre-alloc-groups`` then
``--use-pre-alloc-groups``) and add any failing file to SKIP_FILES.
"""

import ast
import io
import json
import re
import sys
import tokenize
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple

import click

from execution_testing.test_types import (
    EOA,
    compute_create_address,
    keccak256,
)

HEX40_RE = re.compile(r"[0-9a-fA-F]{40}")
HEX64_RE = re.compile(r"\b0[xX][0-9a-fA-F]{64}\b")
HEX_CHARS = set("0123456789abcdefABCDEF")
LOW_RANGE_MAX = 0x100
CREATE_NONCE_RANGE = range(33)
WORD_HEX_LEN = 64  # 32-byte word
RUN_WINDOW = 0x100  # max gap between pins moved together as a run

# Tests whose expectations depend on pinned address values in ways a
# textual consistency rewrite cannot follow; identified by phase-2 fill
# failures at Cancun. Keeping their original addresses is the intended
# fallback and only costs a few pre-alloc groups.
SKIP_FILES = {
    # Storage-asserted gas measurements change when calldata/code
    # address bytes change.
    "tests/ported_static/stEIP150singleCodeGasPrices/test_eip2929.py",
    "tests/ported_static/stEIP150singleCodeGasPrices/test_eip2929_minus_ff.py",  # noqa: E501
    "tests/ported_static/stEIP150singleCodeGasPrices/test_gas_cost_jump.py",  # noqa: E501
    "tests/ported_static/stEIP150Specific/test_transaction64_rule_integer_boundaries.py",  # noqa: E501
    "tests/ported_static/stStaticCall/test_static_create_empty_contract_with_storage_and_call_it_0wei.py",  # noqa: E501
    "tests/ported_static/stCreateTest/test_create_empty_contract_with_storage.py",  # noqa: E501
    "tests/ported_static/stCreateTest/test_create_empty_contract_with_storage_and_call_it_0wei.py",  # noqa: E501
    "tests/ported_static/stCreateTest/test_create_empty_contract_with_storage_and_call_it_1wei.py",  # noqa: E501
    # Expectations derive from address values in ways a textual rewrite
    # cannot follow (dynamic code construction, buffer contents,
    # high-nonce CREATE fan-out, selfdestruct beneficiary balances).
    "tests/ported_static/stDelegatecallTestHomestead/test_delegatecode_dynamic_code.py",  # noqa: E501
    "tests/ported_static/stMemoryTest/test_buffer_src_offset.py",
    "tests/ported_static/vmIOandFlowOperations/test_codecopy.py",
    "tests/ported_static/vmIOandFlowOperations/test_return.py",
    "tests/ported_static/stQuadraticComplexityTest/test_create1000_shnghai.py",  # noqa: E501
    "tests/ported_static/vmTests/test_suicide.py",
    "tests/ported_static/stCreateTest/test_create_oo_gafter_max_codesize.py",  # noqa: E501
    "tests/ported_static/stSystemOperationsTest/test_double_selfdestruct_test.py",  # noqa: E501
    "tests/ported_static/stSystemOperationsTest/test_multi_selfdestruct.py",  # noqa: E501
    # Expectations store a bitwise NOT of a pinned address.
    "tests/ported_static/stRandom/test_random_statetest107.py",
    "tests/ported_static/stRandom/test_random_statetest173.py",
    "tests/ported_static/stRandom/test_random_statetest246.py",
    "tests/ported_static/stRandom/test_random_statetest263.py",
    "tests/ported_static/stRandom/test_random_statetest362.py",
    "tests/ported_static/stRandom/test_random_statetest367.py",
    "tests/ported_static/stRandom/test_random_statetest372.py",
    "tests/ported_static/stRandom/test_random_statetest41.py",
    "tests/ported_static/stRandom/test_random_statetest64.py",
    "tests/ported_static/stRandom/test_random_statetest66.py",
    "tests/ported_static/stRandom2/test_random_statetest437.py",
    "tests/ported_static/stRandom2/test_random_statetest473.py",
    "tests/ported_static/stRandom2/test_random_statetest545.py",
    "tests/ported_static/stRandom2/test_random_statetest564.py",
}

STRING_TOKENS = {tokenize.STRING}
if hasattr(tokenize, "FSTRING_MIDDLE"):  # py312+
    STRING_TOKENS.add(tokenize.FSTRING_MIDDLE)

STRING_INNER_RE = re.compile(
    r"^[rbuRBUfF]{0,2}(\"\"\"|'''|\"|')(.*)\1$", re.DOTALL
)
PURE_HEX_RE = re.compile(r"^(0x)?[0-9a-fA-F]*$")


def push_immediate_spans(code_hex: str) -> List[Tuple[int, int, int]]:
    """
    Linear-disassemble an even-length hex string as EVM bytecode.

    Return (start, end, size) hex-char spans of every PUSH immediate; a
    truncated final immediate is clipped to the end of the string.
    """
    spans = []
    i = 0
    n = len(code_hex)
    while i + 2 <= n:
        op = int(code_hex[i : i + 2], 16)
        i += 2
        if 0x60 <= op <= 0x7F:
            size = op - 0x5F
            spans.append((i, min(i + size * 2, n), size))
            i += size * 2
    return spans


def blob_operand_clear(code_hex: str, start: int, end: int) -> bool:
    """
    Whether hex span [start, end) is clearly an address operand.

    True when the span is exactly a PUSH20 immediate, or the suffix of a
    PUSH21-32 immediate whose leading immediate chars are all zeros.
    """
    for a, b, size in push_immediate_spans(code_hex):
        if size < 20 or end != b or start < a:
            continue
        if b - a != size * 2:
            continue  # truncated push: address is not the low bytes
        if all(ch == "0" for ch in code_hex[a:start]):
            return True
    return False


def eip55(addr: int) -> str:
    """Return the EIP-55 checksummed 40-char hex form of an address."""
    lower = f"{addr:040x}"
    digest = keccak256(lower.encode("ascii")).hex()
    return "".join(
        c.upper() if c.isalpha() and int(digest[i], 16) >= 8 else c
        for i, c in enumerate(lower)
    )


@lru_cache(maxsize=None)
def create_child(addr: int, nonce: int) -> int:
    """Return the CREATE address of `addr` at `nonce` as an int."""
    child = compute_create_address(
        address=addr.to_bytes(20, "big"), nonce=nonce
    )
    return int.from_bytes(bytes(child), "big")


def _number_token_value(text: str) -> Optional[int]:
    """Parse a NUMBER token's value, or None if it is not an integer."""
    try:
        return int(text.replace("_", ""), 0)
    except ValueError:
        return None


def occurrence_style(matched: str, token_text: str) -> str:
    """
    Pick the case style for a rewrite from the matched occurrence.

    All-digit matches (e.g. the `0x1000...` series) carry no case of
    their own, so fall back to the hex letters of the enclosing token (a
    lowercase bytecode blob stays lowercase); default to uppercase, the
    tree's `Address(0x...)` pin style.
    """
    letters = [c for c in matched if c.isalpha()]
    if letters:
        if all(c.islower() for c in letters):
            return "lower"
        if all(c.isupper() for c in letters):
            return "upper"
        return "eip55"
    hex_letters = [c for c in token_text if c in "abcdefABCDEF"]
    if hex_letters and all(c.islower() for c in hex_letters):
        return "lower"
    return "upper"


def style_replacement(style: str, new_addr: int) -> str:
    """Render `new_addr` in the given case style."""
    if style == "lower":
        return f"{new_addr:040x}"
    if style == "upper":
        return f"{new_addr:040X}"
    return eip55(new_addr)


def _derive(relpath: str, addr: int, salt: int) -> int:
    """Hash (relpath, addr, salt) into a 160-bit address."""
    preimage = f"{relpath}:{addr:#042x}"
    if salt:
        preimage += f":{salt}"
    return int.from_bytes(keccak256(preimage.encode("ascii"))[:20], "big")


def derive_address(relpath: str, addr: int, taken: Set[int]) -> int:
    """Derive the deterministic file-private replacement for `addr`."""
    salt = 0
    while True:
        candidate = _derive(relpath, addr, salt)
        if candidate > LOW_RANGE_MAX and candidate not in taken:
            return candidate
        salt += 1


def derive_run(relpath: str, run: List[int], taken: Set[int]) -> List[int]:
    """
    Derive replacements for a run of pins, preserving member offsets.

    The base (lowest) address seeds the hash and every member keeps its
    offset from the base so intra-file address arithmetic stays valid.
    """
    base = run[0]
    salt = 0
    while True:
        new_base = _derive(relpath, base, salt)
        members = [new_base + (a - base) for a in run]
        if (
            new_base > LOW_RANGE_MAX
            and members[-1] < 2**160
            and all(m not in taken for m in members)
        ):
            return members
        salt += 1


class SourceFile:
    """A parsed ported-static test file."""

    def __init__(self, path: Path, root: Path):
        self.path = path
        self.relpath = path.relative_to(root).as_posix()
        self.text = path.read_text(encoding="utf-8")
        self.manually_enhanced = "@manually-enhanced" in self.text
        self.tree = ast.parse(self.text)
        self._line_offsets = self._compute_line_offsets()
        self.tokens = list(
            tokenize.generate_tokens(io.StringIO(self.text).readline)
        )
        self._docstring_lines = self._docstring_line_set()
        # Pins: ints pinned via deploy_contract(address=...); also
        # record pins that are not integer literals (naturally out of
        # scope).
        self.pins: Set[int] = set()
        self.non_literal_pins: List[str] = []
        self._collect_pins()
        # Every 40-hex-char sequence in code tokens (comments and
        # docstrings excluded), as ints, plus value-parsed literals and
        # EOA-key-derived sender addresses; superset used as the
        # potential creator/derived set for the CREATE guard and for
        # the global collision census.
        self.code_hex40: Set[int] = set()
        self.declared_nonces: Set[int] = set()
        self._collect_code_hex40()

    def _compute_line_offsets(self) -> List[int]:
        offsets = [0]
        for line in self.text.splitlines(keepends=True):
            offsets.append(offsets[-1] + len(line))
        return offsets

    def _abs(self, row: int, col: int) -> int:
        return self._line_offsets[row - 1] + col

    def _docstring_line_set(self) -> Set[int]:
        lines: Set[int] = set()
        for node in ast.walk(self.tree):
            if isinstance(
                node,
                (
                    ast.Module,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                body = node.body
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    c = body[0].value
                    lines.update(
                        range(c.lineno, (c.end_lineno or c.lineno) + 1)
                    )
        return lines

    def _collect_pins(self) -> None:
        for node in ast.walk(self.tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "deploy_contract"
            ):
                continue
            for kw in node.keywords:
                if kw.arg != "address":
                    continue
                value = kw.value
                if (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "Address"
                    and value.args
                    and isinstance(value.args[0], ast.Constant)
                ):
                    inner = value.args[0].value
                    if isinstance(inner, int):
                        self.pins.add(inner)
                        continue
                    if isinstance(inner, str):
                        try:
                            self.pins.add(int(inner, 16))
                            continue
                        except ValueError:
                            pass
                elif isinstance(value, ast.Constant) and isinstance(
                    value.value, int
                ):
                    self.pins.add(value.value)
                    continue
                self.non_literal_pins.append(
                    f"line {value.lineno}: {ast.unparse(value)[:80]}"
                )

    def _code_tokens(
        self,
    ) -> Iterator[Tuple[tokenize.TokenInfo, bool]]:
        """Yield (token, is_string) for rewritable code tokens."""
        for tok in self.tokens:
            if tok.type == tokenize.NUMBER:
                yield tok, False
            elif tok.type in STRING_TOKENS:
                if tok.start[0] not in self._docstring_lines:
                    yield tok, True

    def _collect_code_hex40(self) -> None:
        for tok, is_string in self._code_tokens():
            for m in HEX40_RE.finditer(tok.string):
                self.code_hex40.add(int(m.group(), 16))
            if not is_string:
                # Integer literals drop leading zeros, so an address
                # starting with 0x0... can be shorter than 40 hex
                # chars; collect by value as well.
                value = _number_token_value(tok.string)
                if value is not None and 0 < value < 2**160:
                    self.code_hex40.add(value)
        # Senders declared as EOA(key=...) have addresses derived from
        # a 64-hex private key rather than a 40-hex literal; their
        # CREATE children can be pinned collision targets, so add the
        # derived addresses to the creator set.
        for m in HEX64_RE.finditer(self.text):
            try:
                self.code_hex40.add(
                    int.from_bytes(bytes(EOA(key=m.group())), "big")
                )
            except Exception:  # noqa: BLE001 - not a valid key
                pass
        # CREATE children are checked for nonces 0..32 plus any larger
        # nonce literally declared in the file (e.g. high-nonce CREATE
        # tests declare accounts with nonce=2**64-2).
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if (
                        kw.arg == "nonce"
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, int)
                    ):
                        self.declared_nonces.add(kw.value.value)

    def occurrences(self, addr: int) -> List[dict]:
        """
        Find every occurrence of `addr` in rewritable code tokens.

        Each occurrence is classified as clear (safe to rewrite) or
        ambiguous. Clear means the surrounding characters are not hex,
        the only adjacent hex characters are pure left zero-padding
        within a single 32-byte word (the address stored as a word),
        or, for pure-hex bytecode blob strings, a linear EVM
        disassembly places the occurrence exactly as a PUSH20 immediate
        or as the zero-padded low 20 bytes of a PUSH21-32 immediate.
        """
        needle = re.compile(re.escape(f"{addr:040x}"), re.IGNORECASE)
        found = []
        for tok, is_string in self._code_tokens():
            text = tok.string
            if not is_string:
                # Integer literals drop leading zeros, so match NUMBER
                # tokens by value; the plain 40-char scan below would
                # silently miss e.g. 0x95E7BAEA... for 0x095e7baea...
                value = _number_token_value(text)
                if value == addr:
                    is_hex = text.lower().startswith("0x")
                    matched = text[2:] if is_hex else text
                    # A hex literal whose value equals the address is
                    # the address regardless of leading-zero spelling
                    # (a decimal spelling would need a representation
                    # change, so it stays ambiguous). Short literals
                    # like 0x1000 are polysemous; the run-preserving
                    # remap keeps intra-file arithmetic valid and the
                    # fill validation catches misclassified sizes.
                    found.append(
                        {
                            "line": tok.start[0],
                            "abs_start": self._abs(*tok.start)
                            + (2 if is_hex else 0),
                            "match": matched,
                            "context": text.strip()[:100],
                            "clear": is_hex,
                            "style": occurrence_style(matched, text),
                        }
                    )
                    continue
            blob = None  # (hex_string, offset of hex within token)
            if is_string:
                inner_match = STRING_INNER_RE.match(text)
                if inner_match:
                    inner = inner_match.group(2)
                    if PURE_HEX_RE.match(inner) and inner:
                        offset = inner_match.start(2)
                        if inner.lower().startswith("0x"):
                            inner = inner[2:]
                            offset += 2
                        if len(inner) % 2 == 0:
                            blob = (inner.lower(), offset)
                    if (
                        PURE_HEX_RE.match(inner)
                        and inner
                        and len(inner) != 40
                        and _number_token_value("0x" + inner.lstrip("xX0"))
                        == addr
                    ):
                        # Zero-dropped or oddly padded string form of
                        # the address: the 40-char scan cannot rewrite
                        # it, so surface it as ambiguous rather than
                        # silently missing it.
                        found.append(
                            {
                                "line": tok.start[0],
                                "abs_start": self._abs(*tok.start),
                                "match": inner,
                                "context": text.strip()[:100],
                                "clear": False,
                                "style": "upper",
                            }
                        )
                        continue
            for m in needle.finditer(text):
                if blob is not None:
                    hex_str, offset = blob
                    h_start = m.start() - offset
                    h_end = h_start + 40
                    whole = (
                        h_start >= 0
                        and h_end == len(hex_str)
                        and (
                            len(hex_str) <= WORD_HEX_LEN
                            and all(ch == "0" for ch in hex_str[:h_start])
                        )
                    )
                    clear = h_start >= 0 and (
                        whole or blob_operand_clear(hex_str, h_start, h_end)
                    )
                    found.append(
                        {
                            "line": tok.start[0],
                            "abs_start": self._abs(*tok.start) + m.start(),
                            "match": m.group(),
                            "context": text.strip()[:100],
                            "clear": clear,
                            "style": occurrence_style(m.group(), text),
                        }
                    )
                    continue
                before = text[: m.start()]
                after = text[m.end() :]
                prev_hex = bool(before) and before[-1] in HEX_CHARS
                next_hex = bool(after) and after[0] in HEX_CHARS
                clear = not prev_hex and not next_hex
                if prev_hex and not next_hex:
                    # Allow a left-zero-padded 32-byte word: every hex
                    # char to the left, back to the last non-hex char,
                    # is '0', and the whole run is at most 64 chars.
                    run = []
                    for ch in reversed(before):
                        if ch in HEX_CHARS:
                            run.append(ch)
                        else:
                            break
                    if all(ch == "0" for ch in run) and len(run) + 40 <= (
                        WORD_HEX_LEN
                    ):
                        clear = True
                found.append(
                    {
                        "line": tok.start[0],
                        "abs_start": self._abs(*tok.start) + m.start(),
                        "match": m.group(),
                        "context": text.strip()[:100],
                        "clear": clear,
                        "style": occurrence_style(m.group(), text),
                    }
                )
        return found


def load_tree(tree_root: Path, repo_root: Path) -> List[SourceFile]:
    """Parse every test file under `tree_root`."""
    return [
        SourceFile(path, repo_root)
        for path in sorted(tree_root.rglob("test_*.py"))
    ]


def _skip_reason_counts(skips: List[dict]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for s in skips:
        reason = s["reason"]
        if reason.startswith("CREATE address"):
            reason = "CREATE address of a literal in the file"
        elif reason.startswith("its CREATE address"):
            reason = "a literal in the file is its CREATE address"
        elif reason.startswith("run member"):
            reason = "member of a run with an unsafe member"
        counts[reason] += 1
    return dict(counts)


def build_plan(files: List[SourceFile], skip_manually_enhanced: bool) -> dict:
    """Build the full rewrite plan and report."""
    pin_files: Dict[int, List[SourceFile]] = defaultdict(list)
    for f in files:
        for pin in f.pins:
            pin_files[pin].append(f)

    shared = {
        addr: fs
        for addr, fs in pin_files.items()
        if len(fs) > 1 and addr > LOW_RANGE_MAX
    }
    low_shared = sorted(
        addr
        for addr, fs in pin_files.items()
        if len(fs) > 1 and addr <= LOW_RANGE_MAX
    )

    # Global collision domain: every 40-hex sequence anywhere in any
    # file's full text (code, comments, and docstrings alike), plus all
    # newly derived addresses as they are assigned.
    taken: Set[int] = set()
    for f in files:
        for m in HEX40_RE.finditer(f.text):
            taken.add(int(m.group(), 16))

    actions = []  # planned rewrites: one entry per (file, address)
    skips = []  # skipped (file, address) pairs with reasons

    for f in sorted(files, key=lambda s: s.relpath):
        candidates = {a for a in f.pins if a in shared}
        if not candidates:
            continue

        file_reason = None
        if skip_manually_enhanced and f.manually_enhanced:
            file_reason = "manually-enhanced file excluded"
        elif f.relpath in SKIP_FILES:
            file_reason = "fill-failure fallback"
        elif "create2" in f.text.lower():
            file_reason = "file uses CREATE2"
        if file_reason:
            for addr in sorted(candidates):
                skips.append(
                    {
                        "file": f.relpath,
                        "address": f"{addr:#042x}",
                        "reason": file_reason,
                    }
                )
            continue

        nonces = list(CREATE_NONCE_RANGE) + sorted(
            n for n in f.declared_nonces if 32 < n < 2**64
        )
        occurrences_cache: Dict[int, List[dict]] = {}

        def member_guard(
            addr: int,
            f: "SourceFile" = f,
            nonces: List[int] = nonces,
            occurrences_cache: Dict[int, List[dict]] = occurrences_cache,
        ) -> Optional[Tuple[str, List[str]]]:
            """Return (reason, examples) if `addr` is unsafe here."""
            # CREATE-derivation guard, both directions.
            derived_from = [
                (f"{c:#042x}", n)
                for c in f.code_hex40
                for n in nonces
                if create_child(c, n) == addr
            ]
            if derived_from:
                creator, nonce = derived_from[0]
                return (
                    f"CREATE address of {creator} at nonce {nonce}",
                    [],
                )
            derives = [
                (f"{create_child(addr, n):#042x}", n)
                for n in nonces
                if create_child(addr, n) in f.code_hex40
            ]
            if derives:
                child, nonce = derives[0]
                return (
                    f"its CREATE address at nonce {nonce} ({child}) "
                    "is pinned in this file",
                    [],
                )
            occurrences = occurrences_cache.setdefault(
                addr, f.occurrences(addr)
            )
            ambiguous = [o for o in occurrences if not o["clear"]]
            if ambiguous:
                return (
                    "ambiguous occurrence",
                    [
                        f"line {o['line']}: {o['context']}"
                        for o in ambiguous[:3]
                    ],
                )
            return None

        def plan(
            addr: int,
            new_addr: int,
            run_base: Optional[int],
            f: "SourceFile" = f,
            occurrences_cache: Dict[int, List[dict]] = occurrences_cache,
        ) -> dict:
            """Build the action record for one rewritten address."""
            occurrences = occurrences_cache[addr]
            action = {
                "file": f.relpath,
                "address": f"{addr:#042x}",
                "new_address": f"{new_addr:#042x}",
                "occurrences": len(occurrences),
                "manually_enhanced": f.manually_enhanced,
                "_spans": [
                    (o["abs_start"], o["match"], o["style"])
                    for o in occurrences
                ],
            }
            if run_base is not None:
                action["run_base"] = f"{run_base:#042x}"
            return action

        # Group the file's pins into runs of nearby addresses that must
        # move together to keep intra-file address arithmetic valid.
        eligible = sorted(p for p in f.pins if p > LOW_RANGE_MAX)
        runs: List[List[int]] = []
        current: List[int] = []
        for pin in eligible:
            if current and pin - current[-1] <= RUN_WINDOW:
                current.append(pin)
            else:
                if len(current) > 1:
                    runs.append(current)
                current = [pin]
        if len(current) > 1:
            runs.append(current)

        run_members: Set[int] = set()
        for run in runs:
            if not any(a in candidates for a in run):
                continue  # nothing shared: leave the run alone
            run_members.update(run)
            guards = {a: member_guard(a) for a in run}
            failures = {a: g for a, g in guards.items() if g is not None}
            if failures:
                bad_addr, (bad_reason, examples) = next(iter(failures.items()))
                for addr in sorted(a for a in run if a in candidates):
                    skip: dict = {
                        "file": f.relpath,
                        "address": f"{addr:#042x}",
                        "reason": (
                            bad_reason
                            if addr == bad_addr
                            else (
                                f"run member {bad_addr:#042x} unsafe: "
                                f"{bad_reason}"
                            )
                        ),
                    }
                    if addr == bad_addr and examples:
                        skip["examples"] = examples
                    skips.append(skip)
                continue
            new_members = derive_run(f.relpath, run, taken)
            for addr, new_addr in zip(run, new_members, strict=True):
                taken.add(new_addr)
                actions.append(plan(addr, new_addr, run[0]))

        for addr in sorted(candidates - run_members):
            guard = member_guard(addr)
            if guard is not None:
                reason, examples = guard
                single_skip: dict = {
                    "file": f.relpath,
                    "address": f"{addr:#042x}",
                    "reason": reason,
                }
                if examples:
                    single_skip["examples"] = examples
                skips.append(single_skip)
                continue
            new_addr = derive_address(f.relpath, addr, taken)
            taken.add(new_addr)
            actions.append(plan(addr, new_addr, None))

    file_actions: Dict[str, List[dict]] = defaultdict(list)
    for a in actions:
        file_actions[a["file"]].append(a)

    census = {
        "files_scanned": len(files),
        "files_manually_enhanced": sum(
            1 for f in files if f.manually_enhanced
        ),
        "distinct_pinned_addresses": len(pin_files),
        "shared_pinned_addresses": len(shared) + len(low_shared),
        "shared_above_low_range": len(shared),
        "shared_in_low_range": [f"{a:#x}" for a in low_shared],
        "files_pinning_a_shared_address": len(
            {f.relpath for fs in shared.values() for f in fs}
        ),
        "non_literal_pins": {
            f.relpath: f.non_literal_pins for f in files if f.non_literal_pins
        },
    }
    return {
        "census": census,
        "summary": {
            "pairs_planned": len(actions),
            "pairs_skipped": len(skips),
            "files_touched": len(file_actions),
            "files_touched_manually_enhanced": sum(
                1
                for relpath in file_actions
                if any(a["manually_enhanced"] for a in file_actions[relpath])
            ),
            "addresses_fully_privatized": sum(
                1
                for addr in shared
                if not any(s["address"] == f"{addr:#042x}" for s in skips)
            ),
            "skip_reasons": _skip_reason_counts(skips),
        },
        "actions": actions,
        "skips": skips,
    }


def apply_plan(files: List[SourceFile], plan: dict) -> None:
    """Perform the planned rewrites in place."""
    by_file: Dict[str, List[dict]] = defaultdict(list)
    for a in plan["actions"]:
        by_file[a["file"]].append(a)
    files_by_relpath = {f.relpath: f for f in files}
    for relpath, actions in by_file.items():
        f = files_by_relpath[relpath]
        replacements = []
        for a in actions:
            new_addr = int(a["new_address"], 16)
            for abs_start, matched, style in a["_spans"]:
                replacements.append(
                    (abs_start, matched, style_replacement(style, new_addr))
                )
        replacements.sort(reverse=True)
        text = f.text
        for abs_start, matched, replacement in replacements:
            end = abs_start + len(matched)
            assert text[abs_start:end].lower() == matched.lower(), (
                f"span mismatch in {relpath} at offset {abs_start}"
            )
            text = text[:abs_start] + replacement + text[end:]
        ast.parse(text)  # any rewrite that breaks parsing is a bug
        f.path.write_text(text, encoding="utf-8")


def verify_after_apply(tree_root: Path, repo_root: Path, plan: dict) -> int:
    """Re-census the tree; only planned skips may remain shared."""
    files = load_tree(tree_root, repo_root)
    pin_files: Dict[int, List[SourceFile]] = defaultdict(list)
    for f in files:
        for pin in f.pins:
            pin_files[pin].append(f)
    expected_shared = {s["address"] for s in plan["skips"]}
    unexpected = []
    for addr, fs in pin_files.items():
        if len(fs) > 1 and addr > LOW_RANGE_MAX:
            if f"{addr:#042x}" not in expected_shared:
                unexpected.append((f"{addr:#042x}", [f.relpath for f in fs]))
    if unexpected:
        click.echo("UNEXPECTED shared pins remain after apply:")
        for addr_hex, relpaths in unexpected:
            click.echo(f"  {addr_hex}: {relpaths}")
        return 1
    click.echo(
        "post-apply census clean: remaining shared pins are exactly the "
        "planned skips"
    )
    return 0


@click.command()
@click.argument("command", type=click.Choice(["census", "report", "apply"]))
@click.option(
    "--tree",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("tests/ported_static"),
    help="Test tree to rewrite; run from the repository root.",
)
@click.option(
    "--report-file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("tmp/privatize_report.json"),
    help="Where to write the JSON report.",
)
@click.option(
    "--skip-manually-enhanced",
    is_flag=True,
    default=False,
    help="Leave @manually-enhanced files untouched.",
)
def main(
    command: str,
    tree: Path,
    report_file: Path,
    skip_manually_enhanced: bool,
) -> None:
    """
    Rewrite shared pinned addresses in ported static tests to
    file-private ones.
    """
    repo_root = Path.cwd()
    tree = tree.resolve()
    files = load_tree(tree, repo_root)
    plan = build_plan(files, skip_manually_enhanced)

    if command == "census":
        click.echo(json.dumps(plan["census"], indent=2))
        return

    report = dict(plan)
    report["actions"] = [
        {k: v for k, v in a.items() if k != "_spans"} for a in plan["actions"]
    ]
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    click.echo(json.dumps({**plan["census"], **plan["summary"]}, indent=2))
    click.echo(f"report written to {report_file}")

    if command == "apply":
        apply_plan(files, plan)
        click.echo(f"rewrote {plan['summary']['files_touched']} files")
        sys.exit(verify_after_apply(tree, repo_root, plan))


if __name__ == "__main__":
    main()
