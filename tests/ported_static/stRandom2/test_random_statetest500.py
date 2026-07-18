"""
Test_random_statetest500.

Ported from:
state_tests/stRandom2/randomStatetest500Filler.json

@manually-enhanced: Do not overwrite. tx `gas_limit` has been removed.
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
    ["state_tests/stRandom2/randomStatetest500Filler.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_random_statetest500(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_random_statetest500."""
    coinbase = Address(0xD8EB70366571A8EAB0E5FA59CA9AA16F0F36DF99)
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
        address=Address(0xD8EB70366571A8EAB0E5FA59CA9AA16F0F36DF99),  # noqa: E501
    )
    # Source: raw
    # 0x7f000000000000000000000000<contract:0x945304eb96065b2a98b57a48a06ae28d285a71b5>7f000000000000000000000000ffffffffffffffffffffffffffffffffffffffff7f000000000000000000000000ffffffffffffffffffffffffffffffffffffffff817ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe7f00000000000000000000000100000000000000000000000000000000000000007fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff6f87196584968a97046c6791993114825560005155  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.PUSH32[0xD8EB70366571A8EAB0E5FA59CA9AA16F0F36DF99]
        + Op.PUSH32[0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF] * 2
        + Op.DUP2
        + Op.PUSH32[
            0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFE
        ]
        + Op.PUSH32[0x10000000000000000000000000000000000000000]
        + Op.PUSH32[
            0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
        ]
        + Op.SSTORE(
            key=Op.MLOAD(offset=0x0), value=0x87196584968A97046C67919931148255
        ),
        nonce=0,
        address=Address(0x869EFA3F6679D21D5A02396162D019DC6646B502),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(
            "7f000000000000000000000000d8eb70366571a8eab0e5fa59ca9aa16f0f36df997f000000000000000000000000ffffffffffffffffffffffffffffffffffffffff7f000000000000000000000000ffffffffffffffffffffffffffffffffffffffff817ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe7f00000000000000000000000100000000000000000000000000000000000000007fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff6f87196584968a97046c679199311482"  # noqa: E501
        ),
        value=0x20D454F,
    )

    post = {
        target: Account(
            storage={0: 0x87196584968A97046C67919931148255},
            nonce=0,
        ),
        coinbase: Account(storage={}, nonce=0),
        sender: Account(storage={}, code=b"", nonce=1),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
