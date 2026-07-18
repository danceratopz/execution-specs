"""
Test_callcallcodecallcode_011_suicide_middle.

Ported from:
state_tests/stCallDelegateCodesHomestead/callcallcodecallcode_011_SuicideMiddleFiller.json
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
        "state_tests/stCallDelegateCodesHomestead/callcallcodecallcode_011_SuicideMiddleFiller.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcallcodecallcode_011_suicide_middle(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_callcallcodecallcode_011_suicide_middle."""
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
        address=Address(0x36F409006E6695C79AC24224629BD3394D461F17),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALL(
                gas=0x249F0,
                address=0x77F575C64849A1957AB6534E0E4D71CF4FCCF736,
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
        address=Address(0x01B8F82BA8BD8DBDCDB6F1159C852257C17334C1),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (DELEGATECALL 100000 <contract:0x1000000000000000000000000000000000000002> 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.DELEGATECALL(
                gas=0x186A0,
                address=0xB4C9B918297C9A993681E6FCE447868126D39225,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x77F575C64849A1957AB6534E0E4D71CF4FCCF736),  # noqa: E501
    )
    # Source: lll
    # { (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) [[ 2 ]] (DELEGATECALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 64 0 64 ) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SELFDESTRUCT(
            address=0x01B8F82BA8BD8DBDCDB6F1159C852257C17334C1
        )
        + Op.SSTORE(
            key=0x2,
            value=Op.DELEGATECALL(
                gas=0xC350,
                address=0x36F409006E6695C79AC24224629BD3394D461F17,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xB4C9B918297C9A993681E6FCE447868126D39225),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        addr: Account(storage={1: 1}, balance=0),
        addr_2: Account(storage={1: 0, 2: 0}, balance=0x2540BE400),
        addr_3: Account(storage={3: 0}, balance=0x2540BE400),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
