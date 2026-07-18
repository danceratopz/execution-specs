"""
Test_random_statetest115.

Ported from:
state_tests/stRandom/randomStatetest115Filler.json
"""

import pytest
from execution_testing import (
    EOA,
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
    ["state_tests/stRandom/randomStatetest115Filler.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_random_statetest115(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_random_statetest115."""
    coinbase = Address(0xB1C8D7E127E5EA33E238CB7C7FC7C65A67C4EBAD)
    sender = EOA(
        key=0xB1F4CBC3A50042184425A6F9E996D0910F7BA879457CE5DAC5C71E498AD3C005
    )

    env = Environment(
        fee_recipient=coinbase,
        number=1,
        timestamp=1000,
        prev_randao=0x20000,
        base_fee_per_gas=10,
    )

    pre[sender] = Account(balance=0xDE0B6B3A7640000)
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
        address=Address(0xB1C8D7E127E5EA33E238CB7C7FC7C65A67C4EBAD),  # noqa: E501
    )
    # Source: raw
    # 0x7f00000000000000000000000000000000000000000000000000000000000000007f000000000000000000000000<contract:0x945304eb96065b2a98b57a48a06ae28d285a71b5>7f000000000000000000000000000000000000000000000000000000000000c3507f000000000000000000000000000000000000000000000000000000000000c3507f000000000000000000000000<contract:0x945304eb96065b2a98b57a48a06ae28d285a71b5>7f00000000000000000000000000000000000000000000000000000000000000007ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe7f000000000000000000000000000000000000000000000000000000000000c3506f15448e363302150a6f56518aa005315560005155  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.PUSH32[0x0]
        + Op.PUSH32[0xB1C8D7E127E5EA33E238CB7C7FC7C65A67C4EBAD]
        + Op.PUSH32[0xC350] * 2
        + Op.PUSH32[0xB1C8D7E127E5EA33E238CB7C7FC7C65A67C4EBAD]
        + Op.PUSH32[0x0]
        + Op.PUSH32[
            0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFE
        ]
        + Op.PUSH32[0xC350]
        + Op.SSTORE(
            key=Op.MLOAD(offset=0x0), value=0x15448E363302150A6F56518AA0053155
        ),
        nonce=0,
        address=Address(0xB3287F1884B2A2955D0A6FBA5C8F9AD74D939E4E),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(
            "7f00000000000000000000000000000000000000000000000000000000000000007f000000000000000000000000b1c8d7e127e5ea33e238cb7c7fc7c65a67c4ebad7f000000000000000000000000000000000000000000000000000000000000c3507f000000000000000000000000000000000000000000000000000000000000c3507f000000000000000000000000b1c8d7e127e5ea33e238cb7c7fc7c65a67c4ebad7f00000000000000000000000000000000000000000000000000000000000000007ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe7f000000000000000000000000000000000000000000000000000000000000c3506f15448e363302150a6f56518aa00531"  # noqa: E501
        ),
        gas_limit=3202574,
        value=0x74270083,
    )

    post = {
        target: Account(
            storage={0: 0x15448E363302150A6F56518AA0053155},
            nonce=0,
        ),
        coinbase: Account(storage={}, nonce=0),
        sender: Account(storage={}, code=b"", nonce=1),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
