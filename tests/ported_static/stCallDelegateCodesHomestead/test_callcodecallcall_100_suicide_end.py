"""
Test_callcodecallcall_100_suicide_end.

Ported from:
state_tests/stCallDelegateCodesHomestead/callcodecallcall_100_SuicideEndFiller.json

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
        "state_tests/stCallDelegateCodesHomestead/callcodecallcall_100_SuicideEndFiller.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcodecallcall_100_suicide_end(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_callcodecallcall_100_suicide_end."""
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
        address=Address(0xAC5F98328BC3DB1BA407A980575E35C61677BDBA),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (DELEGATECALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.DELEGATECALL(
                address=0x87249D94BF5B5777493303C5C0A02BF7BF55BBFB,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.STOP,
        balance=0xDE0B6B3A7640000,
        nonce=0,
        address=Address(0x08CBBBC5E8DB7541C265E4BFB13D290874F266AE),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALL 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALL(
                address=0xD6A84DCC80D5A62029068A20EA603CC278EB1BC9,
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
        address=Address(0x87249D94BF5B5777493303C5C0A02BF7BF55BBFB),  # noqa: E501
    )
    # Source: lll
    # {  [[ 2 ]] (CALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 0 64 0 64 ) (SELFDESTRUCT <contract:0x1000000000000000000000000000000000000001>) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x2,
            value=Op.CALL(
                address=0xAC5F98328BC3DB1BA407A980575E35C61677BDBA,
                value=0x0,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.SELFDESTRUCT(address=0x87249D94BF5B5777493303C5C0A02BF7BF55BBFB)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xD6A84DCC80D5A62029068A20EA603CC278EB1BC9),  # noqa: E501
    )

    tx = Transaction(sender=sender, to=target, data=Bytes(""))

    post = {
        target: Account(storage={0: 1, 1: 1, 2: 0}),
        addr: Account(storage={1: 0, 3: 0}),
        addr_2: Account(storage={2: 1}, balance=0),
        addr_3: Account(storage={3: 1}),
        sender: Account(storage={1: 0, 2: 0}),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
