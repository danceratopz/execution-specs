"""
CALLCODE -> CALL -> (CALLCODE -> code) (suicide).

Ported from:
state_tests/stCallCodes/callcodecallcallcode_101_SuicideEndFiller.json

@manually-enhanced: Do not overwrite. Explicit gas values removed.
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
    ["state_tests/stCallCodes/callcodecallcallcode_101_SuicideEndFiller.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcodecallcallcode_101_suicide_end(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """CALLCODE -> CALL -> (CALLCODE -> code) (suicide)."""
    coinbase = Address(0x2ADC25665018AA1FE0E6BC666DAC8FC2697FF9BA)
    sender = pre.fund_eoa(amount=0xDE0B6B3A7640000)

    env = Environment(
        fee_recipient=coinbase,
        number=1,
        timestamp=1000,
        prev_randao=0x20000,
        base_fee_per_gas=10,
        gas_limit=30000000,
    )

    # Source: lll
    # {  (SSTORE 3 1) }
    addr_3 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x3, value=0x1) + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x1581ADA030218CE8505A91ECE10413FC7CA3974F),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALLCODE 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALLCODE(
                address=0x408166AED1E96A234E791AF579DDB24D91C742E9,
                value=0x0,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.STOP,
        balance=0xDE0B6B3A7640000,
        nonce=0,
        address=Address(0x1DD9CE5C464AF1843FE18CCBCB271E5A201A4129),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALL 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALL(
                address=0x3E03710E9130F9C32FD438D97BBFB3318D339E7F,
                value=0x0,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x408166AED1E96A234E791AF579DDB24D91C742E9),  # noqa: E501
    )
    # Source: lll
    # {  [[ 2 ]] (CALLCODE 50000 <contract:0x1000000000000000000000000000000000000003> 0 0 64 0 64 ) (SELFDESTRUCT <contract:0x1000000000000000000000000000000000000001>) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x2,
            value=Op.CALLCODE(
                address=0x1581ADA030218CE8505A91ECE10413FC7CA3974F,
                value=0x0,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.SELFDESTRUCT(address=0x408166AED1E96A234E791AF579DDB24D91C742E9)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x3E03710E9130F9C32FD438D97BBFB3318D339E7F),  # noqa: E501
    )

    tx = Transaction(sender=sender, to=target, data=Bytes(""))

    post = {
        target: Account(storage={0: 1, 1: 1}),
        addr: Account(storage={2: 0}, balance=0x4A817C800),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
