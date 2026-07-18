"""
Test_random_statetest30.

Ported from:
state_tests/stRandom/randomStatetest30Filler.json
"""

import pytest
from execution_testing import (
    Account,
    Address,
    Alloc,
    Bytes,
    Environment,
    StateTestFiller,
    Transaction,
)
from execution_testing.vm import Op

REFERENCE_SPEC_GIT_PATH = "N/A"
REFERENCE_SPEC_VERSION = "N/A"


@pytest.mark.ported_from(
    ["state_tests/stRandom/randomStatetest30Filler.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_random_statetest30(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_random_statetest30."""
    coinbase = Address(0x0296C6927FF77EB0DCAE5BE3CE25D093E51ED7CB)
    sender = pre.fund_eoa(amount=0xDE0B6B3A7640000)

    env = Environment(
        fee_recipient=coinbase,
        number=1,
        timestamp=1000,
        prev_randao=0x20000,
        base_fee_per_gas=10,
    )

    # Source: raw
    # 0x41314155
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=Op.COINBASE, value=Op.BALANCE(address=Op.COINBASE)),
        balance=0xDE0B6B3A7640000,
        nonce=0,
    )
    # Source: raw
    # 0x6000355415600957005b60203560003555
    coinbase = pre.deploy_contract(  # noqa: F841
        code=Op.JUMPI(
            pc=0x9,
            condition=Op.ISZERO(Op.SLOAD(key=Op.CALLDATALOAD(offset=0x0))),
        )
        + Op.STOP
        + Op.JUMPDEST
        + Op.SSTORE(
            key=Op.CALLDATALOAD(offset=0x0), value=Op.CALLDATALOAD(offset=0x20)
        ),
        balance=46,
        nonce=0,
        address=Address(0x0296C6927FF77EB0DCAE5BE3CE25D093E51ED7CB),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes("42"),
        gas_limit=400000,
        value=0x186A0,
    )

    post = {
        target: Account(
            storage={0x0296C6927FF77EB0DCAE5BE3CE25D093E51ED7CB: 46},
            nonce=0,
        ),
        coinbase: Account(storage={}, nonce=0),
        sender: Account(storage={}, code=b"", nonce=1),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
