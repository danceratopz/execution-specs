"""
Test_static_callcallcodecall_010_suicide_middle2.

Ported from:
state_tests/stStaticCall/static_callcallcodecall_010_SuicideMiddle2Filler.json
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
        "state_tests/stStaticCall/static_callcallcodecall_010_SuicideMiddle2Filler.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.slow
@pytest.mark.pre_alloc_mutable
def test_static_callcallcodecall_010_suicide_middle2(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_static_callcallcodecall_010_suicide_middle2."""
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
    # {  (MSTORE 3 1) }
    addr_3 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(offset=0x3, value=0x1) + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xE04B95AA34E0D3B096A385B9DA8A7784405E171C),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (STATICCALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 64 0 64 ) [[ 1 ]] 1 }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.STATICCALL(
                gas=0x249F0,
                address=0x88FF6D81763384AC0690462F736E99A7F857DBF3,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.SSTORE(key=0x1, value=0x1)
        + Op.STOP,
        balance=0xDE0B6B3A7640000,
        nonce=0,
        address=Address(0xBF00B5A5326CB4FCBC52FE2BE7151E5466EA1C72),  # noqa: E501
    )
    # Source: lll
    # {  (CALLCODE 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.CALLCODE(
            gas=0x186A0,
            address=0x3067340A86635609C0FB48AA01AE5160C855038B,
            value=0x0,
            args_offset=0x0,
            args_size=0x40,
            ret_offset=0x0,
            ret_size=0x40,
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x88FF6D81763384AC0690462F736E99A7F857DBF3),  # noqa: E501
    )
    # Source: lll
    # {  (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) (STATICCALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 64 0 64 ) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SELFDESTRUCT(
            address=0xBF00B5A5326CB4FCBC52FE2BE7151E5466EA1C72
        )
        + Op.STATICCALL(
            gas=0xC350,
            address=0xE04B95AA34E0D3B096A385B9DA8A7784405E171C,
            args_offset=0x0,
            args_size=0x40,
            ret_offset=0x0,
            ret_size=0x40,
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x3067340A86635609C0FB48AA01AE5160C855038B),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        target: Account(storage={0: 1, 1: 1}),
        addr_2: Account(storage={1: 0, 2: 0}, balance=0x2540BE400),
        addr_3: Account(storage={3: 0}, balance=0x2540BE400),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
