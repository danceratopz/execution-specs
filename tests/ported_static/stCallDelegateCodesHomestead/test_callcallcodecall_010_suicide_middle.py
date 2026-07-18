"""
Test_callcallcodecall_010_suicide_middle.

Ported from:
state_tests/stCallDelegateCodesHomestead/callcallcodecall_010_SuicideMiddleFiller.json
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
        "state_tests/stCallDelegateCodesHomestead/callcallcodecall_010_SuicideMiddleFiller.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcallcodecall_010_suicide_middle(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_callcallcodecall_010_suicide_middle."""
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
        address=Address(0xD80140F5F571AE513BE93425D9D988D6E0581C86),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALL(
                gas=0x249F0,
                address=0xAF2A72B5E1BA49E02A93797244EB7EF16EA7B8A1,
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
        address=Address(0xD8B4FC0A2C1B50839D517E1EC66CDE5F9DB5180C),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (DELEGATECALL 100000 <contract:0x1000000000000000000000000000000000000002> 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.DELEGATECALL(
                gas=0x186A0,
                address=0x201C626C135046CE41E06E90EB7217212144501B,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xAF2A72B5E1BA49E02A93797244EB7EF16EA7B8A1),  # noqa: E501
    )
    # Source: lll
    # {  (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) [[ 2 ]] (CALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 0 64 0 64 ) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SELFDESTRUCT(
            address=0xD8B4FC0A2C1B50839D517E1EC66CDE5F9DB5180C
        )
        + Op.SSTORE(
            key=0x2,
            value=Op.CALL(
                gas=0xC350,
                address=0xD80140F5F571AE513BE93425D9D988D6E0581C86,
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
        address=Address(0x201C626C135046CE41E06E90EB7217212144501B),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        target: Account(storage={0: 1}, balance=0xDE0B6B5FB6FE400),
        addr: Account(storage={1: 1}, balance=0),
        addr_3: Account(storage={2: 0, 3: 0}, balance=0x2540BE400),
        sender: Account(storage={2: 0, 3: 0}),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
