"""
CALLCODE -> CALLCODE -> (CALLCODE -> code) suicide.

Ported from:
state_tests/stCallCodes/callcodecallcodecallcode_111_SuicideEndFiller.json

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
    [
        "state_tests/stCallCodes/callcodecallcodecallcode_111_SuicideEndFiller.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcodecallcodecallcode_111_suicide_end(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """CALLCODE -> CALLCODE -> (CALLCODE -> code) suicide."""
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
        address=Address(0xEAF8A9F70775CEE0E492987B526A761AB8EBAE00),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALLCODE 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALLCODE(
                address=0xF01FBEB82133421F1945A17DDDB4673E6BA51AD1,
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
        address=Address(0x69411817547BE3F4C04597CFA6C8E111134F60CB),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALLCODE 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALLCODE(
                address=0xF83E563B1F7D772B40FDC0004FDCB6A298418138,
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
        address=Address(0xF01FBEB82133421F1945A17DDDB4673E6BA51AD1),  # noqa: E501
    )
    # Source: lll
    # {  [[ 2 ]] (CALLCODE 50000 <contract:0x1000000000000000000000000000000000000003> 0 0 64 0 64 ) (SELFDESTRUCT <contract:0x1000000000000000000000000000000000000001>) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x2,
            value=Op.CALLCODE(
                address=0xEAF8A9F70775CEE0E492987B526A761AB8EBAE00,
                value=0x0,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.SELFDESTRUCT(address=0xF01FBEB82133421F1945A17DDDB4673E6BA51AD1)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xF83E563B1F7D772B40FDC0004FDCB6A298418138),  # noqa: E501
    )

    tx = Transaction(sender=sender, to=target, data=Bytes(""))

    post = {
        addr: Account(balance=0xDE0B6B5FB6FE400),
        addr_2: Account(storage={0: 0, 1: 0, 2: 0}, balance=0x2540BE400),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
