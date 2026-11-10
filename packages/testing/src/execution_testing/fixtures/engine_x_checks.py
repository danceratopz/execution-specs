"""
Fill-time execution-consistency checks for the grouped fixture formats.

An Engine X fixture is filled against its packed pre-allocation group's
merged genesis, while the test's `blockchain_test_engine` sibling is
filled against the test's own pre-allocation. Their per-payload
execution outputs must be identical; `verify_engine_x_execution`
compares the two fixture trees after a fill and raises a classified,
per-cause report when they are not.

The check runs post-fill on the fixture files because the two formats of
a test are separate pytest items that may fill on different xdist
workers; the output directory is the only place both reliably exist. It
only needs that directory, so it can also be re-run standalone against a
failed fill's artifacts without re-filling.

`verify_blockchain_x_execution` does the same for the RLP blocks and the
post state of `blockchain_test_x` fixtures against their `blockchain_test`
siblings. That format covers the groups of the forks before Paris, which
have no Engine X fixtures.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Type, TypeVar

from pydantic import ValidationError

from execution_testing.base_types import Account, Address, Alloc, Bytes, Hash
from execution_testing.forks import Byzantium
from execution_testing.forks.forks.eips.prague.eip_2935 import (
    HISTORY_STORAGE_ADDRESS,
)
from execution_testing.test_types import AllocGroupHash
from execution_testing.test_types.block_access_list import BlockAccessList

from .blockchain import (
    BlockchainEngineFixture,
    BlockchainEngineXFixture,
    BlockchainFixture,
    BlockchainXFixture,
    FixtureBlock,
    FixtureEngineNewPayload,
    FixtureExecutionPayload,
    InvalidFixtureBlock,
)
from .pre_alloc_groups import PreAllocGroup, PreAllocGroups

ENGINE_X_FIXTURES_DIR = BlockchainEngineXFixture.output_base_dir_name()
SIBLING_FIXTURES_DIR = BlockchainEngineFixture.output_base_dir_name()
BLOCKCHAIN_X_FIXTURES_DIR = BlockchainXFixture.output_base_dir_name()
BLOCKCHAIN_FIXTURES_DIR = BlockchainFixture.output_base_dir_name()

# Path parts under a fixture format tree that do not contain fixture
# files (mirrors INDEX_EXCLUDED_PATH_PARTS in `cli/gen_index.py`).
_NON_FIXTURE_PATH_PARTS = frozenset({".meta", "pre_alloc"})

# Execution payload fields whose value is a function of the genesis
# state root and so legitimately differs between a test's own genesis
# and its packed group's genesis. Python field names of
# `FixtureExecutionPayload`; a unit test asserts they stay valid when
# the model changes.
STATE_ROOT_DERIVED_FIELDS = frozenset(
    {"state_root", "block_hash", "parent_hash"}
)

# Placeholder for the masked EIP-2935 parent-hash write in a BAL.
_PARENT_HASH_PLACEHOLDER = "<parent-hash>"

_VALUE_DISPLAY_LIMIT = 96

# Block header fields whose value is a function of the genesis state root
# (`ommers_hash` through the uncle headers, which are compared with these
# fields masked). Python field names of `FixtureHeader`; a unit test
# asserts they stay valid when the model changes.
GENESIS_DERIVED_HEADER_FIELDS = frozenset(
    {"state_root", "block_hash", "parent_hash", "ommers_hash"}
)

_FixtureT = TypeVar(
    "_FixtureT",
    BlockchainEngineFixture,
    BlockchainEngineXFixture,
    BlockchainFixture,
    BlockchainXFixture,
)


class EngineXCheckError(Exception):
    """The Engine X execution check failed to run on the fixture output."""


@dataclass(frozen=True)
class ExecutionDrift:
    """A fixture whose packed execution differs from its sibling's."""

    test_id: str
    signature: str
    """One-line cause classification; identical causes share it."""
    detail: str
    """Multi-line explanation rendered for the first example only."""


class EngineXExecutionDriftError(EngineXCheckError):
    """
    A packed pre-allocation group changed a test's execution.

    Either an account introduced by pre-alloc group packing leaked into
    the test's execution (see `pack_pre_alloc_groups`), or the test
    observes a block hash (e.g. via `BLOCKHASH`), which depends on every
    account in the genesis and so cannot survive any grouping. Drifts
    are grouped by cause signature so a single systemic cause reads as
    one diagnosis, not one failure per fixture.
    """

    MAX_SIGNATURES = 10
    MAX_EXAMPLE_IDS = 3

    def __init__(
        self,
        drifts: List[ExecutionDrift],
        compared: int,
        label: str = "Engine X",
    ):
        """Initialize with per-fixture drifts, grouped by signature."""
        self.drifts = drifts
        self.compared = compared
        grouped: Dict[str, List[ExecutionDrift]] = {}
        for drift in drifts:
            grouped.setdefault(drift.signature, []).append(drift)
        sections = []
        for signature, group in list(grouped.items())[: self.MAX_SIGNATURES]:
            ids = ", ".join(
                drift.test_id for drift in group[: self.MAX_EXAMPLE_IDS]
            )
            if len(group) > self.MAX_EXAMPLE_IDS:
                ids += f", ... and {len(group) - self.MAX_EXAMPLE_IDS} more"
            section = f"[{len(group)}x] {signature}\n  tests: {ids}"
            if group[0].detail:
                section += "\n" + "\n".join(
                    f"  {line}" for line in group[0].detail.splitlines()
                )
            sections.append(section)
        if len(grouped) > self.MAX_SIGNATURES:
            sections.append(
                f"... and {len(grouped) - self.MAX_SIGNATURES} more "
                "distinct causes"
            )
        super().__init__(
            f"{len(drifts)} of {compared} {label} fixtures execute "
            "differently against their packed pre-allocation group's "
            "genesis than against their own pre-allocation "
            f"({len(grouped)} distinct cause(s)):\n\n" + "\n\n".join(sections)
        )


@dataclass(frozen=True)
class EngineXCheckResult:
    """Outcome of a completed Engine X execution check."""

    compared: int = 0
    skipped: int = 0
    skip_reason: str | None = None
    """Set when fixtures of the format exist but nothing was compared."""
    label: str = "Engine X"

    @property
    def summary(self) -> str:
        """Return a one-line summary of the check for the fill log."""
        summary = (
            f"{self.compared} {self.label} fixtures execute identically "
            "against their packed group's genesis"
        )
        if self.skipped:
            summary += f" ({self.skipped} skipped: no sibling fixture)"
        return summary


def _sibling_test_id(
    grouped_test_id: str, grouped_format: str, sibling_format: str
) -> str:
    """Return the id of a grouped fixture's sibling in the other format."""
    return grouped_test_id.replace(grouped_format, sibling_format)


def _sibling_file(
    grouped_file: Path,
    grouped_dir: Path,
    sibling_dir: Path,
    grouped_format: str,
    sibling_format: str,
) -> Path:
    """
    Return the sibling fixture file for a grouped fixture file.

    A `--single-fixture-per-file` fill embeds the fixture format name in
    every file name, so the sibling's basename can differ.
    """
    sibling = sibling_dir / grouped_file.relative_to(grouped_dir)
    if not sibling.exists():
        sibling = sibling.with_name(
            sibling.name.replace(grouped_format, sibling_format)
        )
    return sibling


def _fixture_files(fixtures_dir: Path) -> List[Path]:
    """Return the fixture files of a format tree, without group files."""
    return [
        file
        for file in sorted(fixtures_dir.rglob("*.json"))
        if not _NON_FIXTURE_PATH_PARTS.intersection(
            file.relative_to(fixtures_dir).parts
        )
    ]


def _load_fixture_file(
    file: Path, fixture_cls: Type[_FixtureT]
) -> Dict[str, _FixtureT]:
    """Parse every fixture in a fixture file with its typed model."""
    try:
        raw = json.loads(file.read_text())
    except json.JSONDecodeError as e:
        raise EngineXCheckError(f"unreadable fixture file {file}: {e}") from e
    fixtures: Dict[str, _FixtureT] = {}
    for test_id, data in raw.items():
        try:
            fixtures[test_id] = fixture_cls.model_validate(data)
        except ValidationError as e:
            raise EngineXCheckError(
                f"cannot parse {fixture_cls.format_name!r} fixture "
                f"{test_id!r} in {file}: {e}"
            ) from e
    return fixtures


def _comparable_payload(payload: FixtureEngineNewPayload) -> Dict[str, Any]:
    """
    Return the payload as a dict without state-root-derived values.

    The block access list is replaced by its decoded, parent-hash-masked
    form, see `_comparable_bal`.
    """
    entry = payload.model_dump(
        mode="json",
        by_alias=True,
        exclude={
            "params": {
                0: set(STATE_ROOT_DERIVED_FIELDS) | {"block_access_list"}
            }
        },
    )
    execution_payload = payload.params[0]
    if execution_payload.block_access_list is not None:
        entry["params"][0]["blockAccessList"] = _comparable_bal(
            execution_payload.block_access_list,
            execution_payload.parent_hash,
        )
    return entry


def _comparable_bal(bal: Bytes, parent_hash: Hash) -> Any:
    """
    Return the decoded BAL with the EIP-2935 history write masked.

    The EIP-2935 system call writes the block's parent hash into the
    history contract on every block; at payload 0 that value is the
    genesis hash itself, so it is the one BAL entry that legitimately
    differs between a test's own genesis and its packed group's genesis.
    Only that write is masked: a storage change of the history contract
    whose written value equals the payload's own parent hash. A
    parent-hash-valued write to any other account is genuine drift (the
    test observes block hashes and cannot survive grouping). An
    undecodable BAL (an intentionally malformed one from a negative
    test) is compared verbatim.

    Known limitation: a header parent hash injected with
    `Block.rlp_modifier=Header(parent_hash=...)` defeats the mask. The
    override is applied after t8n has executed the block, so the BAL
    keeps the real parent hash while the payload field holds the
    injected value; the mask matches neither, and the check fails
    loudly on a difference that packing did not cause. No test does
    this today. If one appears, isolate it with
    `@pytest.mark.pre_alloc_group("separate")`, or make the mask derive
    the expected value from the chain itself (the genesis hash at
    payload 0, the previous payload's block hash after that) instead of
    the payload's own `parent_hash` field.
    """
    try:
        accounts = BlockAccessList.from_rlp(bal)
    except Exception:
        return str(bal)
    parent_hash_value = int.from_bytes(parent_hash, "big")
    dumped = accounts.model_dump(mode="json")
    for account in dumped:
        if int(account["address"], 16) != HISTORY_STORAGE_ADDRESS:
            continue
        for slot in account["storage_changes"]:
            for change in slot["slot_changes"]:
                if int(change["post_value"], 16) == parent_hash_value:
                    change["post_value"] = _PARENT_HASH_PLACEHOLDER
    return dumped


class _GroupLookup:
    """Lazily load packed pre-allocation groups for drift attribution."""

    def __init__(self, engine_x_dir: Path):
        """Initialize with the Engine X fixture tree to look under."""
        self._folder = engine_x_dir / "pre_alloc"
        self._groups: PreAllocGroups | None = None

    def get(self, pre_hash: AllocGroupHash) -> PreAllocGroup | None:
        """Return the group for a hash, or None if unavailable."""
        if self._groups is None:
            if not self._folder.is_dir():
                return None
            try:
                self._groups = PreAllocGroups.from_folder(
                    self._folder, lazy_load=True
                )
            except Exception:
                return None
        try:
            return self._groups[pre_hash]
        except Exception:
            return None


def _short(value: Any) -> str:
    """Render a value for an error message, truncated if long."""
    text = value if isinstance(value, str) else json.dumps(value)
    if len(text) > _VALUE_DISPLAY_LIMIT:
        text = f"{text[:_VALUE_DISPLAY_LIMIT]}... ({len(text)} chars)"
    return text


def _hex_int(value: Any) -> int | None:
    """Parse a hex string to an int, or return None."""
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return None


def _diff_fields(
    base_entry: Dict[str, Any], packed_entry: Dict[str, Any]
) -> List[Tuple[str, Any, Any]]:
    """Return the (field, own, packed) diffs of two comparable payloads."""
    diffs: List[Tuple[str, Any, Any]] = []
    for key in sorted(set(base_entry) | set(packed_entry)):
        base_value = base_entry.get(key)
        packed_value = packed_entry.get(key)
        if base_value == packed_value:
            continue
        if (
            key != "params"
            or not isinstance(base_value, list)
            or not isinstance(packed_value, list)
            or len(base_value) != len(packed_value)
        ):
            diffs.append((key, base_value, packed_value))
            continue
        for i, (base_param, packed_param) in enumerate(
            zip(base_value, packed_value, strict=True)
        ):
            if base_param == packed_param:
                continue
            if (
                i == 0
                and isinstance(base_param, dict)
                and isinstance(packed_param, dict)
            ):
                for field in sorted(set(base_param) | set(packed_param)):
                    if base_param.get(field) != packed_param.get(field):
                        diffs.append(
                            (
                                field,
                                base_param.get(field),
                                packed_param.get(field),
                            )
                        )
            else:
                diffs.append((f"params[{i}]", base_param, packed_param))
    return diffs


def _parent_hash_write_slot(
    base_account: Dict[str, Any],
    packed_account: Dict[str, Any],
    base_parent_hash: int,
    packed_parent_hash: int,
) -> str | None:
    """Return the slot where each side stored its own parent hash."""
    packed_slots = {
        slot["slot"]: slot for slot in packed_account["storage_changes"]
    }
    for base_slot in base_account["storage_changes"]:
        packed_slot = packed_slots.get(base_slot["slot"])
        if packed_slot is None:
            continue
        packed_changes = {
            change["block_access_index"]: change
            for change in packed_slot["slot_changes"]
        }
        for base_change in base_slot["slot_changes"]:
            packed_change = packed_changes.get(
                base_change["block_access_index"]
            )
            if packed_change is None or base_change == packed_change:
                continue
            if (
                _hex_int(base_change["post_value"]) == base_parent_hash
                and _hex_int(packed_change["post_value"]) == packed_parent_hash
            ):
                return str(base_slot["slot"])
    return None


def _diff_bal(
    payload_index: int,
    base_bal: Any,
    packed_bal: Any,
    base_payload: FixtureExecutionPayload,
    packed_payload: FixtureExecutionPayload,
    sibling: BlockchainEngineFixture,
    engine_x: BlockchainEngineXFixture,
    groups: _GroupLookup,
) -> Tuple[str, str]:
    """Return (signature, detail) for a block-access-list difference."""
    prefix = f"payload {payload_index}"
    if isinstance(base_bal, str) or isinstance(packed_bal, str):
        return (
            f"{prefix}: blockAccessList differs (undecodable BAL "
            "compared verbatim)",
            f"own:    {_short(base_bal)}\npacked: {_short(packed_bal)}",
        )
    base_accounts = {account["address"]: account for account in base_bal}
    packed_accounts = {account["address"]: account for account in packed_bal}
    extra = sorted(set(packed_accounts) - set(base_accounts))
    missing = sorted(set(base_accounts) - set(packed_accounts))
    if extra:
        address = extra[0]
        signature = (
            f"{prefix}: account {address} appears in the packed "
            "fixture's BAL only"
        )
        if Address(address) in sibling.pre.root:
            return signature, (
                "the account is declared in the test's own "
                "pre-allocation but only touched under the packed "
                "genesis: packing changed the execution path"
            )
        group = groups.get(engine_x.pre_hash)
        if group is not None and Address(address) in group.pre:
            others = ", ".join(group.test_ids[:3])
            return signature, (
                "the account is absent from the test's own "
                "pre-allocation but present in pre-alloc group "
                f"{engine_x.pre_hash} ({group.test_count} tests, e.g. "
                f"{others}): an account introduced by packing leaked "
                "into this test's execution. Isolate the test with "
                '@pytest.mark.pre_alloc_group("separate") or declare '
                "the account in its pre-allocation"
            )
        return signature, (
            "the account is absent from the test's own pre-allocation "
            "and from its packed pre-alloc group: packing changed the "
            "execution path"
        )
    if missing:
        return (
            f"{prefix}: account {missing[0]} is missing from the "
            "packed fixture's BAL",
            "the test touches the account only under its own genesis: "
            "packing changed the execution path",
        )
    base_parent_hash = int.from_bytes(base_payload.parent_hash, "big")
    packed_parent_hash = int.from_bytes(packed_payload.parent_hash, "big")
    for address, base_account in base_accounts.items():
        packed_account = packed_accounts[address]
        if base_account == packed_account:
            continue
        slot = _parent_hash_write_slot(
            base_account,
            packed_account,
            base_parent_hash,
            packed_parent_hash,
        )
        if slot is not None:
            return (
                f"{prefix}: account {address} writes its block's "
                f"parent hash to storage (slot {slot})",
                "each fixture's BAL stores its own parent hash: the "
                "test observes block hashes (e.g. via BLOCKHASH), "
                "which cannot survive pre-alloc grouping. Isolate the "
                'test with @pytest.mark.pre_alloc_group("separate")',
            )
        return (
            f"{prefix}: BAL differs for account {address}",
            f"own:    {_short(base_account)}\n"
            f"packed: {_short(packed_account)}",
        )
    return f"{prefix}: blockAccessList differs", ""


def _diagnose(
    test_id: str,
    engine_x: BlockchainEngineXFixture,
    sibling: BlockchainEngineFixture,
    base_payloads: List[Dict[str, Any]],
    packed_payloads: List[Dict[str, Any]],
    groups: _GroupLookup,
) -> ExecutionDrift:
    """Classify the first difference between two payload sequences."""
    if len(base_payloads) != len(packed_payloads):
        return ExecutionDrift(
            test_id,
            signature="payload count differs",
            detail=(
                f"sibling has {len(base_payloads)} payloads, packed "
                f"fixture has {len(packed_payloads)}: packing changed "
                "block-level outcomes"
            ),
        )
    for index, (base_entry, packed_entry) in enumerate(
        zip(base_payloads, packed_payloads, strict=True)
    ):
        if base_entry == packed_entry:
            continue
        diffs = _diff_fields(base_entry, packed_entry)
        fields = sorted({field for field, _, _ in diffs})
        if "blockAccessList" in fields:
            base_bal, packed_bal = next(
                (base_value, packed_value)
                for field, base_value, packed_value in diffs
                if field == "blockAccessList"
            )
            signature, detail = _diff_bal(
                index,
                base_bal,
                packed_bal,
                sibling.payloads[index].params[0],
                engine_x.payloads[index].params[0],
                sibling,
                engine_x,
                groups,
            )
            other_fields = [f for f in fields if f != "blockAccessList"]
            if other_fields:
                detail += (
                    f"\nthe payload also differs in: {', '.join(other_fields)}"
                )
            return ExecutionDrift(test_id, signature, detail)
        detail_lines = []
        for field, base_value, packed_value in diffs[:5]:
            detail_lines.append(f"{field}:")
            detail_lines.append(f"  own:    {_short(base_value)}")
            detail_lines.append(f"  packed: {_short(packed_value)}")
        return ExecutionDrift(
            test_id,
            signature=f"payload {index} differs in: {', '.join(fields)}",
            detail="\n".join(detail_lines),
        )
    return ExecutionDrift(test_id, "payloads differ", "")


def verify_engine_x_execution(output_dir: Path) -> EngineXCheckResult:
    """
    Verify that pre-alloc group packing did not change any test's
    execution.

    For every Engine X fixture (filled against its packed group's merged
    genesis), compare its payloads against the test's
    `blockchain_test_engine` sibling fixture (filled against the test's
    own pre-allocation in the same session, with an independent `t8n`
    execution: Engine X fixtures never share the transition tool output
    cache). All payload fields except the state-root-derived ones must
    match exactly; each payload's block access list is compared with the
    EIP-2935 history write of its own parent hash masked out, see
    `_comparable_bal`.

    Return the comparison counts; `skip_reason` is set when Engine X
    fixtures exist but nothing could be compared (e.g. when filling with
    `-m blockchain_test_engine_x`, which produces no siblings).

    Raise `EngineXExecutionDriftError` if any test executed differently,
    or `EngineXCheckError` if a fixture file cannot be parsed.
    """
    engine_x_dir = output_dir / ENGINE_X_FIXTURES_DIR
    sibling_dir = output_dir / SIBLING_FIXTURES_DIR
    engine_x_files = _fixture_files(engine_x_dir)
    if not engine_x_files:
        # Possibly only the pre-allocation groups, which other grouped
        # formats (`blockchain_test_x`) share.
        return EngineXCheckResult()
    if not sibling_dir.is_dir():
        return EngineXCheckResult(
            skip_reason=(
                "Engine X execution consistency check skipped: this "
                f"fill generated no {SIBLING_FIXTURES_DIR} fixtures to "
                "compare against (e.g. filling with `-m "
                f"{BlockchainEngineXFixture.format_name}`). Leaks from "
                "pre-alloc group packing are not verified for this "
                "output."
            )
        )

    groups = _GroupLookup(engine_x_dir)
    compared = 0
    skipped = 0
    drifts: List[ExecutionDrift] = []
    for engine_x_file in engine_x_files:
        sibling_file = _sibling_file(
            engine_x_file,
            engine_x_dir,
            sibling_dir,
            BlockchainEngineXFixture.format_name,
            BlockchainEngineFixture.format_name,
        )
        siblings = (
            _load_fixture_file(sibling_file, BlockchainEngineFixture)
            if sibling_file.exists()
            else {}
        )
        for test_id, fixture in _load_fixture_file(
            engine_x_file, BlockchainEngineXFixture
        ).items():
            sibling = siblings.get(
                _sibling_test_id(
                    test_id,
                    BlockchainEngineXFixture.format_name,
                    BlockchainEngineFixture.format_name,
                )
            )
            if sibling is None:
                skipped += 1
                continue
            compared += 1
            base = [_comparable_payload(p) for p in sibling.payloads]
            packed = [_comparable_payload(p) for p in fixture.payloads]
            if base != packed:
                drifts.append(
                    _diagnose(test_id, fixture, sibling, base, packed, groups)
                )

    if drifts:
        raise EngineXExecutionDriftError(drifts, compared)
    skip_reason = None
    if compared == 0 and skipped > 0:
        skip_reason = (
            "Engine X execution consistency check skipped: none of the "
            f"{skipped} Engine X fixtures have a {SIBLING_FIXTURES_DIR} "
            "sibling fixture to compare against. Leaks from pre-alloc "
            "group packing are not verified for this output."
        )
    return EngineXCheckResult(
        compared=compared, skipped=skipped, skip_reason=skip_reason
    )


def _comparable_block(
    block: FixtureBlock | InvalidFixtureBlock, *, mask_receipts_root: bool
) -> Dict[str, Any]:
    """
    Return the block as a dict without genesis-derived values.

    Besides the header fields in `GENESIS_DERIVED_HEADER_FIELDS` (also in
    each uncle header), the block's `rlp` is left out, and so is each
    receipt's `post_state` and the `rlp` built from it. Before Byzantium a
    receipt's `post_state` is the state root after its transaction, which
    derives from the genesis; from Byzantium on it is unset, so leaving it
    out changes nothing. `mask_receipts_root` leaves out the header's
    `receipts_root`, which commits to those state roots before Byzantium.
    """
    header = set(GENESIS_DERIVED_HEADER_FIELDS)
    if mask_receipts_root:
        header.add("receipts_root")
    content: Dict[Any, Any] = {
        "header": header,
        "ommers": {"__all__": header},
        "receipts": {"__all__": {"post_state", "rlp_field"}},
    }
    if isinstance(block, InvalidFixtureBlock):
        return block.model_dump(
            mode="json",
            by_alias=True,
            exclude={"rlp": True, "rlp_decoded": content},
        )
    return block.model_dump(
        mode="json", by_alias=True, exclude={"rlp": True, **content}
    )


def _diagnose_blocks(
    test_id: str,
    own_blocks: List[Dict[str, Any]],
    packed_blocks: List[Dict[str, Any]],
) -> ExecutionDrift:
    """Classify the first difference between two block sequences."""
    if len(own_blocks) != len(packed_blocks):
        return ExecutionDrift(
            test_id,
            signature="block count differs",
            detail=(
                f"sibling has {len(own_blocks)} blocks, packed fixture "
                f"has {len(packed_blocks)}"
            ),
        )
    for index, (own, packed) in enumerate(
        zip(own_blocks, packed_blocks, strict=True)
    ):
        if own == packed:
            continue
        own_exception = own.get("expectException")
        packed_exception = packed.get("expectException")
        if own_exception != packed_exception:
            return ExecutionDrift(
                test_id,
                signature=f"block {index} expects a different exception",
                detail=(
                    f"own:    {own_exception or 'valid'}\n"
                    f"packed: {packed_exception or 'valid'}"
                ),
            )
        diffs = [
            (f"blockHeader.{field}", own_value, packed_value)
            for field, own_value, packed_value in _diff_fields(
                own.get("blockHeader", {}), packed.get("blockHeader", {})
            )
        ] + [
            (field, own.get(field), packed.get(field))
            for field in sorted(set(own) | set(packed))
            if field != "blockHeader" and own.get(field) != packed.get(field)
        ]
        fields = [field for field, _, _ in diffs]
        detail_lines = []
        for field, own_value, packed_value in diffs[:5]:
            detail_lines.append(f"{field}:")
            detail_lines.append(f"  own:    {_short(own_value)}")
            detail_lines.append(f"  packed: {_short(packed_value)}")
        detail_lines.append(
            "an account introduced by packing leaked into the test, or the "
            "test observes a block hash (e.g. via BLOCKHASH), which depends "
            "on the genesis. Isolate the test with "
            '@pytest.mark.pre_alloc_group("separate") or declare the '
            "account in its pre-allocation"
        )
        return ExecutionDrift(
            test_id,
            signature=f"block {index} differs in: {', '.join(fields)}",
            detail="\n".join(detail_lines),
        )
    return ExecutionDrift(test_id, "blocks differ", "")


def _comparable_account(account: Account | None) -> Any:
    """
    Return an account's state as plain values, or None if it is absent.

    Storage slots holding zero are left out: a slot set to zero is not
    stored.
    """
    if account is None:
        return None
    return {
        "nonce": int(account.nonce),
        "balance": int(account.balance),
        "code": account.code.hex(),
        "storage": {
            int(key): int(value)
            for key, value in account.storage.root.items()
            if int(value) != 0
        },
    }


def _diagnose_post_state(
    test_id: str,
    own_pre: Alloc,
    own_post: Alloc,
    group_pre: Alloc,
    post_state_diff: Alloc,
) -> ExecutionDrift | None:
    """
    Compare a fixture's post state with its sibling's full post state.

    The fixture's post state is the group's `pre` with `post_state_diff`
    applied. On the accounts of the sibling's own test (those of its `pre`
    and its post state) it must equal the sibling's post state, and every
    account the diff names must be in that state as the diff has it.
    Accounts of the group that the test did not touch are not compared.
    """

    def packed_account(address: Address) -> Any:
        if address in post_state_diff.root:
            return _comparable_account(post_state_diff.root[address])
        return _comparable_account(group_pre.root.get(address))

    def own_account(address: Address) -> Any:
        return _comparable_account(own_post.root.get(address))

    addresses = dict.fromkeys(
        [*own_post.root, *own_pre.root, *post_state_diff.root]
    )
    for address in addresses:
        own, packed = own_account(address), packed_account(address)
        if own == packed:
            continue
        if own is None:
            signature = "packed post state has an account the sibling's lacks"
        elif packed is None:
            signature = "packed post state lacks an account of the sibling's"
        else:
            signature = "packed post state differs in an account"
        return ExecutionDrift(
            test_id,
            signature=signature,
            detail=(
                f"account {address}:\n"
                f"  own:    {_short(own)}\n"
                f"  packed: {_short(packed)}\n"
                "the packed post state is the group's pre with "
                "postStateDiff applied; an account introduced by packing "
                "leaked into the test, or the diff is wrong"
            ),
        )
    return None


def verify_blockchain_x_execution(output_dir: Path) -> EngineXCheckResult:
    """
    Verify that pre-alloc group packing did not change the execution of
    any `blockchain_test_x` fixture.

    Compare each fixture's blocks against the test's `blockchain_test`
    sibling, which was filled against the test's own pre-allocation. All
    block fields except the genesis-derived ones (see
    `_comparable_block`) must match exactly, and invalid blocks must
    expect the same exception. When the sibling has a full post state,
    the group's `pre` with the fixture's `postStateDiff` applied must
    match it as well (see `_diagnose_post_state`).

    Raise `EngineXExecutionDriftError` if any test executed differently,
    or `EngineXCheckError` if a fixture file or a fixture's group cannot
    be read.
    """
    label = "Blockchain Test X"
    x_dir = output_dir / BLOCKCHAIN_X_FIXTURES_DIR
    sibling_dir = output_dir / BLOCKCHAIN_FIXTURES_DIR
    x_files = _fixture_files(x_dir)
    if not x_files:
        return EngineXCheckResult(label=label)
    if not sibling_dir.is_dir():
        return EngineXCheckResult(
            label=label,
            skip_reason=(
                f"{label} execution consistency check skipped: this fill "
                f"generated no {BLOCKCHAIN_FIXTURES_DIR} fixtures to compare "
                "against. Leaks from pre-alloc group packing are not "
                "verified for this output."
            ),
        )
    # Both grouped formats keep their groups under the Engine X tree.
    groups = _GroupLookup(output_dir / ENGINE_X_FIXTURES_DIR)
    compared = 0
    skipped = 0
    drifts: List[ExecutionDrift] = []
    x_name = BlockchainXFixture.format_name
    sibling_name = BlockchainFixture.format_name
    for x_file in x_files:
        sibling_file = _sibling_file(
            x_file, x_dir, sibling_dir, x_name, sibling_name
        )
        siblings = (
            _load_fixture_file(sibling_file, BlockchainFixture)
            if sibling_file.exists()
            else {}
        )
        for test_id, fixture in _load_fixture_file(
            x_file, BlockchainXFixture
        ).items():
            sibling = siblings.get(
                _sibling_test_id(test_id, x_name, sibling_name)
            )
            if sibling is None:
                skipped += 1
                continue
            compared += 1
            mask_receipts_root = (
                fixture.fork.fork_at(block_number=0, timestamp=0) < Byzantium
            )
            own = [
                _comparable_block(b, mask_receipts_root=mask_receipts_root)
                for b in sibling.blocks
            ]
            packed = [
                _comparable_block(b, mask_receipts_root=mask_receipts_root)
                for b in fixture.blocks
            ]
            if own != packed:
                drifts.append(_diagnose_blocks(test_id, own, packed))
                continue
            if sibling.post_state is None:
                # The sibling only has a post-state hash, which derives
                # from its own genesis.
                continue
            group = groups.get(fixture.pre_hash)
            if group is None:
                raise EngineXCheckError(
                    f"pre-allocation group {fixture.pre_hash} of {test_id} "
                    f"is missing from {ENGINE_X_FIXTURES_DIR}/pre_alloc"
                )
            drift = _diagnose_post_state(
                test_id,
                own_pre=sibling.pre,
                own_post=sibling.post_state,
                group_pre=group.pre,
                post_state_diff=fixture.post_state_diff,
            )
            if drift is not None:
                drifts.append(drift)

    if drifts:
        raise EngineXExecutionDriftError(drifts, compared, label=label)
    skip_reason = None
    if compared == 0 and skipped > 0:
        skip_reason = (
            f"{label} execution consistency check skipped: none of the "
            f"{skipped} {label} fixtures have a {BLOCKCHAIN_FIXTURES_DIR} "
            "sibling fixture to compare against. Leaks from pre-alloc "
            "group packing are not verified for this output."
        )
    return EngineXCheckResult(
        compared=compared,
        skipped=skipped,
        skip_reason=skip_reason,
        label=label,
    )
