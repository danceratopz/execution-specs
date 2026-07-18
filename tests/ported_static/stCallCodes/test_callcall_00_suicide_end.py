"""
Call -> (call -> code) suicide.

Ported from:
state_tests/stCallCodes/callcall_00_SuicideEndFiller.json

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
    ["state_tests/stCallCodes/callcall_00_SuicideEndFiller.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcall_00_suicide_end(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Call -> (call -> code) suicide ."""
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
        address=Address(0xB5179FA1FA6170266DD88232FA8526B9B9A0928D),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALL(
                address=0x8EB02CC59CDC46312F24D0F6C5E8CD607E7DD8FC,
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
        address=Address(0xBACCBBB2B8C0FA3F6FAF632E9C68CDAE23DA8030),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALL 50000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALL(
                address=0xB5179FA1FA6170266DD88232FA8526B9B9A0928D,
                value=0x0,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.SELFDESTRUCT(address=0xBACCBBB2B8C0FA3F6FAF632E9C68CDAE23DA8030)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x8EB02CC59CDC46312F24D0F6C5E8CD607E7DD8FC),  # noqa: E501
    )

    tx = Transaction(sender=sender, to=target, data=Bytes(""))

    post = {
        target: Account(balance=0xDE0B6B5FB6FE400),
        addr_2: Account(storage={2: 1}, balance=0x2540BE400),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
