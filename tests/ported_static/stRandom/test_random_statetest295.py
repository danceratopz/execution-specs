"""
Test_random_statetest295.

Ported from:
state_tests/stRandom/randomStatetest295Filler.json
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
    ["state_tests/stRandom/randomStatetest295Filler.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_random_statetest295(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_random_statetest295."""
    coinbase = Address(0x4770D159A9E2B8C7809EC49BA48B411B5DEA2CD2)
    sender = pre.fund_eoa(amount=0xDE0B6B3A7640000)

    env = Environment(
        fee_recipient=coinbase,
        number=1,
        timestamp=1000,
        prev_randao=0x20000,
        base_fee_per_gas=10,
        gas_limit=9223372036854775807,
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
        address=Address(0x4770D159A9E2B8C7809EC49BA48B411B5DEA2CD2),  # noqa: E501
    )
    # Source: raw
    # 0x7f000000000000000000000000<contract:0x945304eb96065b2a98b57a48a06ae28d285a71b5>7f000000000000000000000000<contract:0x945304eb96065b2a98b57a48a06ae28d285a71b5>7f000000000000000000000000000000000000000000000000000000000000c3507ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe7f000000000000000000000000000000000000000000000000000000000000c3507fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f000000000000000000000000000000000000000000000000000000000000c3507f000000000000000000000000<contract:0x945304eb96065b2a98b57a48a06ae28d285a71b5>31353a0b3c8b17eb55  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=bytes.fromhex(
            "7f0000000000000000000000004770d159a9e2b8c7809ec49ba48b411b5dea2cd27f0000000000000000000000004770d159a9e2b8c7809ec49ba48b411b5dea2cd27f000000000000000000000000000000000000000000000000000000000000c3507ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe7f000000000000000000000000000000000000000000000000000000000000c3507fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f000000000000000000000000000000000000000000000000000000000000c3507f0000000000000000000000004770d159a9e2b8c7809ec49ba48b411b5dea2cd231353a0b3c8b17eb55"  # noqa: E501
        ),
        nonce=0,
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(
            "7f0000000000000000000000004770d159a9e2b8c7809ec49ba48b411b5dea2cd27f0000000000000000000000004770d159a9e2b8c7809ec49ba48b411b5dea2cd27f000000000000000000000000000000000000000000000000000000000000c3507ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe7f000000000000000000000000000000000000000000000000000000000000c3507fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f000000000000000000000000000000000000000000000000000000000000c3507f0000000000000000000000004770d159a9e2b8c7809ec49ba48b411b5dea2cd231353a0b3c8b17eb"  # noqa: E501
        ),
        gas_limit=100000,
        value=0x23044B23,
    )

    post = {
        target: Account(storage={}, balance=0, nonce=0),
        coinbase: Account(storage={}, nonce=0),
        sender: Account(storage={}, code=b"", nonce=1),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
