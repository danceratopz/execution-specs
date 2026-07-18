"""
Test_callcodecallcall_100_suicide_middle.

Ported from:
state_tests/stCallDelegateCodesCallCodeHomestead/callcodecallcall_100_SuicideMiddleFiller.json
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
        "state_tests/stCallDelegateCodesCallCodeHomestead/callcodecallcall_100_SuicideMiddleFiller.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcodecallcall_100_suicide_middle(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_callcodecallcall_100_suicide_middle."""
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
        address=Address(0x25AF66C5BC98686DB9030C6AC1673F0C3E93B616),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (DELEGATECALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.DELEGATECALL(
                gas=0x249F0,
                address=0x387304FA5924BE4004F8B65643495FCCDB3CD203,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.STOP,
        balance=0xDE0B6B3A7640000,
        nonce=0,
        address=Address(0xF4CA4631C5FE7CD97C5332B8FD55FCA777D4CCE8),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALLCODE 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALLCODE(
                gas=0x186A0,
                address=0x6434C62373E9CAA2728804C1C8095C5B69F6EF36,
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
        address=Address(0x387304FA5924BE4004F8B65643495FCCDB3CD203),  # noqa: E501
    )
    # Source: lll
    # {  (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) [[ 2 ]] (CALLCODE 50000 <contract:0x1000000000000000000000000000000000000003> 0 0 64 0 64 ) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SELFDESTRUCT(
            address=0xF4CA4631C5FE7CD97C5332B8FD55FCA777D4CCE8
        )
        + Op.SSTORE(
            key=0x2,
            value=Op.CALLCODE(
                gas=0xC350,
                address=0x25AF66C5BC98686DB9030C6AC1673F0C3E93B616,
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
        address=Address(0x6434C62373E9CAA2728804C1C8095C5B69F6EF36),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        target: Account(storage={0: 1, 1: 1}),
        addr_2: Account(storage={0: 0, 1: 0}),
        addr_3: Account(storage={3: 0}, balance=0x2540BE400),
        sender: Account(storage={1: 0}),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
