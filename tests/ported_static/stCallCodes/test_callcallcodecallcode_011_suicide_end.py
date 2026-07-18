"""
Call -> callcode ->  (callcode -> code) (suicide).

Ported from:
state_tests/stCallCodes/callcallcodecallcode_011_SuicideEndFiller.json
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
    ["state_tests/stCallCodes/callcallcodecallcode_011_SuicideEndFiller.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcallcodecallcode_011_suicide_end(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Call -> callcode ->  (callcode -> code) (suicide)."""
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
        address=Address(0x1AA39D86487406EB4F01A4265C275EED34DDDCAE),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALL(
                gas=0x249F0,
                address=0xDCBC2119AB36AD9E81DCBFAA765544A18AC0DDAB,
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
        address=Address(0x392BDCCD91E28B6D14401477B439C5A6740D93F5),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALLCODE 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALLCODE(
                gas=0x186A0,
                address=0xBAD7672B8EB022E20C81FA79FB32BD499584B884,
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
        address=Address(0xDCBC2119AB36AD9E81DCBFAA765544A18AC0DDAB),  # noqa: E501
    )
    # Source: lll
    # {  [[ 2 ]] (CALLCODE 50000 <contract:0x1000000000000000000000000000000000000003> 0 0 64 0 64 ) (SELFDESTRUCT <contract:0x1000000000000000000000000000000000000001>) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x2,
            value=Op.CALLCODE(
                gas=0xC350,
                address=0x1AA39D86487406EB4F01A4265C275EED34DDDCAE,
                value=0x0,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.SELFDESTRUCT(address=0xDCBC2119AB36AD9E81DCBFAA765544A18AC0DDAB)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xBAD7672B8EB022E20C81FA79FB32BD499584B884),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {addr_2: Account(storage={1: 0, 2: 0, 3: 0}, balance=0x2540BE400)}

    state_test(env=env, pre=pre, post=post, tx=tx)
