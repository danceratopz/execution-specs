"""
Call -> (callcode  -> code) suicide.

Ported from:
state_tests/stCallCodes/callcallcode_01_SuicideEndFiller.json
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
    ["state_tests/stCallCodes/callcallcode_01_SuicideEndFiller.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcallcode_01_suicide_end(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Call -> (callcode  -> code) suicide."""
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
    # {  (SSTORE 2 1) }
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x2, value=0x1) + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xD4CB222A4A4D4D9E68078E1DA39721AEC39B0546),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALL(
                gas=0x249F0,
                address=0xF3465FF8457D51044A0A0288EBC3003836476B23,
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
        address=Address(0xBCEFB64D71ED9D0D5A1D80DA5C570A627DD9BEB7),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALLCODE 50000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALLCODE(
                gas=0xC350,
                address=0xD4CB222A4A4D4D9E68078E1DA39721AEC39B0546,
                value=0x0,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.SELFDESTRUCT(address=0xBCEFB64D71ED9D0D5A1D80DA5C570A627DD9BEB7)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xF3465FF8457D51044A0A0288EBC3003836476B23),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        target: Account(balance=0xDE0B6B5FB6FE400),
        addr_2: Account(storage={2: 0}, balance=0x2540BE400),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
