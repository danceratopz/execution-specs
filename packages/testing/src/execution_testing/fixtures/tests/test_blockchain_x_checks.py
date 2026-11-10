"""Tests for the Blockchain Test X execution-consistency check."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from execution_testing.base_types import Address, Bytes, Hash
from execution_testing.exceptions import BlockException
from execution_testing.forks import Byzantium, Frontier
from execution_testing.test_types import (
    Account,
    Alloc,
    AllocGroupHash,
    Environment,
)

from ..blockchain import (
    BlockchainFixture,
    BlockchainXFixture,
    FixtureBlock,
    FixtureBlockBase,
    FixtureConfig,
    FixtureHeader,
    InvalidFixtureBlock,
)
from ..engine_x_checks import (
    BLOCKCHAIN_FIXTURES_DIR,
    BLOCKCHAIN_X_FIXTURES_DIR,
    ENGINE_X_FIXTURES_DIR,
    GENESIS_DERIVED_HEADER_FIELDS,
    EngineXCheckError,
    EngineXExecutionDriftError,
    verify_blockchain_x_execution,
)
from ..pre_alloc_groups import PreAllocGroupBuilder

X_ID = "tests/a.py::test_a[fork_{fork}-blockchain_test_x]"
OWN_ID = "tests/a.py::test_a[fork_{fork}-blockchain_test]"

# Each format's genesis differs by its state root: the group's genesis
# holds every account of the group.
OWN_GENESIS_ROOT = Hash(0x1)
GROUP_GENESIS_ROOT = Hash(0x2)
RECEIPTS_ROOT = Hash(0x10)
PRE_HASH = "0x0123456789abcdef"
LEAK_HINT = 'pre_alloc_group("separate")'

# A test's own accounts: a sender and a contract whose pre holds a
# storage slot set to zero, which a post state does not list.
SENDER = Address(0x1000)
CONTRACT = Address(0x2000)
CREATED = Address(0x3000)
OTHER_TEST = Address(0x4000)
OWN_PRE = Alloc(
    {
        SENDER: Account(nonce=0, balance=10**18),
        CONTRACT: Account(code=b"\x00", storage={1: 0, 2: 7}),
    }
)
OWN_POST = Alloc(
    {
        SENDER: Account(nonce=1, balance=10**18 - 21_000),
        CONTRACT: Account(code=b"\x00", storage={2: 7}),
        CREATED: Account(balance=1),
    }
)
# The group also holds the accounts of the other tests it packs.
GROUP_PRE = Alloc({**OWN_PRE.root, OTHER_TEST: Account(balance=5)})
POST_STATE_DIFF = Alloc(
    {
        SENDER: Account(nonce=1, balance=10**18 - 21_000),
        CREATED: Account(balance=1),
    }
)


def _block(
    fork: Any, *, genesis_root: Hash, gas_used: int, receipts_root: Hash
) -> FixtureBlock:
    """Build block 1 on top of a genesis with the given state root."""
    genesis = FixtureHeader.genesis(
        fork, Environment().set_fork_requirements(fork), genesis_root
    )
    header = genesis.model_copy(
        update={
            "number": 1,
            "parent_hash": genesis.block_hash,
            "state_root": Hash(int.from_bytes(genesis_root, "big") + 0x10),
            "gas_used": gas_used,
            "receipts_root": receipts_root,
        }
    )
    return FixtureBlockBase(header=header).with_rlp(txs=[])


def _write(
    root: Path,
    fork: Any,
    *,
    packed_gas_used: int = 21_000,
    packed_receipts_root: Hash = RECEIPTS_ROOT,
    invalid: bool = False,
    packed_exception: BlockException = BlockException.INCORRECT_BLOCK_FORMAT,
    with_sibling: bool = True,
    extra_packed_block: bool = False,
    own_post: Alloc | None = None,
    post_state_diff: Alloc | None = None,
    with_group: bool = True,
) -> None:
    """
    Write one test's blockchain_test and blockchain_test_x fixtures.

    With `own_post`, the sibling carries its full post state, and the
    group of the fixture is written too.
    """
    own_block: FixtureBlock | InvalidFixtureBlock = _block(
        fork,
        genesis_root=OWN_GENESIS_ROOT,
        gas_used=21_000,
        receipts_root=RECEIPTS_ROOT,
    )
    packed_block: FixtureBlock | InvalidFixtureBlock = _block(
        fork,
        genesis_root=GROUP_GENESIS_ROOT,
        gas_used=packed_gas_used,
        receipts_root=packed_receipts_root,
    )
    if invalid:
        assert isinstance(own_block, FixtureBlock)
        assert isinstance(packed_block, FixtureBlock)
        own_block = InvalidFixtureBlock(
            rlp=own_block.rlp,
            expect_exception=BlockException.INCORRECT_BLOCK_FORMAT,
            rlp_decoded=own_block.without_rlp(),
        )
        packed_block = InvalidFixtureBlock(
            rlp=packed_block.rlp,
            expect_exception=packed_exception,
            rlp_decoded=packed_block.without_rlp(),
        )
    common: Dict[str, Any] = {
        "fork": fork,
        "genesis_rlp": Bytes(b"\x01"),
        "last_block_hash": Hash(0),
        "config": FixtureConfig(fork=fork),
    }
    own = BlockchainFixture(
        genesis=FixtureHeader.genesis(
            fork, Environment().set_fork_requirements(fork), OWN_GENESIS_ROOT
        ),
        blocks=[own_block],
        pre=OWN_PRE if own_post is not None else Alloc(),
        post_state=own_post,
        post_state_hash=Hash(0) if own_post is None else None,
        **common,
    )
    packed_blocks: List[FixtureBlock | InvalidFixtureBlock] = [packed_block]
    if extra_packed_block:
        packed_blocks.append(packed_block)
    packed = BlockchainXFixture(
        genesis=FixtureHeader.genesis(
            fork, Environment().set_fork_requirements(fork), GROUP_GENESIS_ROOT
        ),
        blocks=packed_blocks,
        pre_hash=AllocGroupHash(PRE_HASH),
        post_state_diff=post_state_diff
        or Alloc({Address(0x1000): Account(balance=1)}),
        **common,
    )
    if own_post is not None and with_group:
        _write_group(root, fork, test_id=X_ID.format(fork=fork.name()))
    name = fork.name()
    for directory, test_id, fixture in [
        (BLOCKCHAIN_X_FIXTURES_DIR, X_ID, packed),
        (BLOCKCHAIN_FIXTURES_DIR, OWN_ID, own),
    ]:
        if directory == BLOCKCHAIN_FIXTURES_DIR and not with_sibling:
            continue
        path = root / directory / f"for_{name.lower()}" / "a" / "test_a.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({test_id.format(fork=name): fixture.json_dict})
        )


def _write_group(root: Path, fork: Any, *, test_id: str) -> None:
    """Write the fixture's pre-allocation group, as phase 1 would."""
    folder = root / ENGINE_X_FIXTURES_DIR / "pre_alloc"
    folder.mkdir(parents=True, exist_ok=True)
    builder = PreAllocGroupBuilder(
        test_ids=[test_id],
        environment=Environment().set_fork_requirements(fork),
        fork=fork,
        pre=GROUP_PRE,
        group_hash=AllocGroupHash(PRE_HASH),
    )
    (folder / f"{PRE_HASH}.json").write_text(
        builder.build().model_dump_json(by_alias=True, exclude_none=True)
    )


def test_identical_execution_passes(tmp_path: Path) -> None:
    """Blocks that differ only in genesis-derived values match."""
    _write(tmp_path, Frontier)

    result = verify_blockchain_x_execution(tmp_path)

    assert result.compared == 1
    assert result.skip_reason is None
    assert "Blockchain Test X" in result.summary


def test_execution_drift_raises(tmp_path: Path) -> None:
    """A block that executes differently in its group is reported."""
    _write(tmp_path, Frontier, packed_gas_used=42_000)

    with pytest.raises(EngineXExecutionDriftError) as exc_info:
        verify_blockchain_x_execution(tmp_path)

    message = str(exc_info.value)
    assert "1 of 1 Blockchain Test X fixtures" in message
    assert "blockHeader.gasUsed" in message
    assert LEAK_HINT in message


def test_block_count_drift_raises_without_leak_hint(tmp_path: Path) -> None:
    """A different number of blocks is drift, but not a block content one."""
    _write(tmp_path, Frontier, extra_packed_block=True)

    with pytest.raises(EngineXExecutionDriftError) as exc_info:
        verify_blockchain_x_execution(tmp_path)

    message = str(exc_info.value)
    assert "block count differs" in message
    assert LEAK_HINT not in message


@pytest.mark.parametrize("fork,masked", [(Frontier, True), (Byzantium, False)])
def test_receipts_root_masked_before_byzantium(
    tmp_path: Path, fork: Any, masked: bool
) -> None:
    """Receipts carry a state root, and so the genesis, before Byzantium."""
    _write(tmp_path, fork, packed_receipts_root=Hash(0x99))

    if masked:
        assert verify_blockchain_x_execution(tmp_path).compared == 1
    else:
        with pytest.raises(EngineXExecutionDriftError):
            verify_blockchain_x_execution(tmp_path)


def test_invalid_blocks_compare_their_exception(tmp_path: Path) -> None:
    """An invalid block must expect the same exception in both formats."""
    _write(tmp_path, Frontier, invalid=True)
    assert verify_blockchain_x_execution(tmp_path).compared == 1


def test_invalid_block_exception_drift_raises(tmp_path: Path) -> None:
    """A different expected exception is drift, with its own diagnosis."""
    _write(
        tmp_path,
        Frontier,
        invalid=True,
        packed_exception=BlockException.INVALID_GAS_USED,
    )
    with pytest.raises(EngineXExecutionDriftError) as exc_info:
        verify_blockchain_x_execution(tmp_path)

    message = str(exc_info.value)
    assert "block 0 expects a different exception" in message
    assert "INVALID_GAS_USED" in message
    assert LEAK_HINT not in message


def test_post_state_matches_the_sibling(tmp_path: Path) -> None:
    """
    The group's pre with the diff applied equals the sibling's post state
    on the test's accounts; the other tests' accounts are not compared.
    """
    _write(
        tmp_path, Frontier, own_post=OWN_POST, post_state_diff=POST_STATE_DIFF
    )
    assert verify_blockchain_x_execution(tmp_path).compared == 1


@pytest.mark.parametrize(
    "post_state_diff,signature",
    [
        pytest.param(
            Alloc(
                {
                    **POST_STATE_DIFF.root,
                    SENDER: Account(nonce=1, balance=10**18 - 21_001),
                }
            ),
            "packed post state differs in an account",
            id="tampered_balance",
        ),
        pytest.param(
            Alloc({**POST_STATE_DIFF.root, OTHER_TEST: Account(balance=6)}),
            "packed post state has an account the sibling's lacks",
            id="leaked_account",
        ),
        pytest.param(
            Alloc({**POST_STATE_DIFF.root, CONTRACT: None}),
            "packed post state lacks an account of the sibling's",
            id="deleted_account_the_sibling_keeps",
        ),
        pytest.param(
            Alloc({SENDER: POST_STATE_DIFF.root[SENDER]}),
            "packed post state lacks an account of the sibling's",
            id="missing_created_account",
        ),
    ],
)
def test_post_state_drift_raises(
    tmp_path: Path, post_state_diff: Alloc, signature: str
) -> None:
    """A diff that does not reproduce the sibling's post state is drift."""
    _write(
        tmp_path, Frontier, own_post=OWN_POST, post_state_diff=post_state_diff
    )

    with pytest.raises(EngineXExecutionDriftError) as exc_info:
        verify_blockchain_x_execution(tmp_path)

    assert signature in str(exc_info.value)


def test_post_state_deletion_must_be_in_the_diff(tmp_path: Path) -> None:
    """An account the sibling's test removed must be removed by the diff."""
    own_post = Alloc(
        {
            address: account
            for address, account in OWN_POST.root.items()
            if address != CONTRACT
        }
    )
    _write(
        tmp_path, Frontier, own_post=own_post, post_state_diff=POST_STATE_DIFF
    )

    with pytest.raises(EngineXExecutionDriftError) as exc_info:
        verify_blockchain_x_execution(tmp_path)
    assert "has an account the sibling's lacks" in str(exc_info.value)

    tmp_path_fixed = tmp_path / "fixed"
    _write(
        tmp_path_fixed,
        Frontier,
        own_post=own_post,
        post_state_diff=Alloc({**POST_STATE_DIFF.root, CONTRACT: None}),
    )
    assert verify_blockchain_x_execution(tmp_path_fixed).compared == 1


def test_post_state_needs_the_group(tmp_path: Path) -> None:
    """A fixture whose group file is missing cannot be checked."""
    _write(
        tmp_path,
        Frontier,
        own_post=OWN_POST,
        post_state_diff=POST_STATE_DIFF,
        with_group=False,
    )
    with pytest.raises(EngineXCheckError, match=PRE_HASH):
        verify_blockchain_x_execution(tmp_path)


def test_no_sibling_tree_sets_skip_reason(tmp_path: Path) -> None:
    """Without blockchain_test fixtures there is nothing to compare."""
    _write(tmp_path, Frontier, with_sibling=False)

    result = verify_blockchain_x_execution(tmp_path)

    assert result.compared == 0
    assert result.skip_reason is not None
    assert BLOCKCHAIN_FIXTURES_DIR in result.skip_reason


def test_no_blockchain_x_fixtures_is_silent(tmp_path: Path) -> None:
    """A fill without the format has nothing to check or warn."""
    result = verify_blockchain_x_execution(tmp_path)

    assert result.compared == 0
    assert result.skip_reason is None


def test_genesis_derived_fields_exist_on_the_header_model() -> None:
    """The exclusion set must track `FixtureHeader` renames."""
    fields = set(FixtureHeader.model_fields) | set(
        FixtureHeader.model_computed_fields
    )
    assert GENESIS_DERIVED_HEADER_FIELDS <= fields
    assert "receipts_root" in fields
