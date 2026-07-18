"""
Test_static_callcodecallcall_100_suicide_end2.

Ported from:
state_tests/stStaticCall/static_callcodecallcall_100_SuicideEnd2Filler.json
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
        "state_tests/stStaticCall/static_callcodecallcall_100_SuicideEnd2Filler.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.slow
@pytest.mark.pre_alloc_mutable
def test_static_callcodecallcall_100_suicide_end2(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_static_callcodecallcall_100_suicide_end2."""
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
        address=Address(0x7F8A5E4DD96679590BF7CD94FC6B97C8A9C89E95),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALLCODE 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) [[ 1 ]] 1 }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALLCODE(
                gas=0x249F0,
                address=0x7C7E7E04B71CEF12B6F4B3340E8E81E513166EC2,
                value=0x0,
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
        address=Address(0x66227CF0A560E1F6F9E94345DD1B5C6758923BA6),  # noqa: E501
    )
    # Source: lll
    # {  (MSTORE 3 1) (STATICCALL 100000 <contract:0x1000000000000000000000000000000000000002> 0 64 0 64 ) (MSTORE 32 1) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(offset=0x3, value=0x1)
        + Op.POP(
            Op.STATICCALL(
                gas=0x186A0,
                address=0x5A092B1C6583FE51BD9772742A333657BAF42C6B,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            )
        )
        + Op.MSTORE(offset=0x20, value=0x1)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x7C7E7E04B71CEF12B6F4B3340E8E81E513166EC2),  # noqa: E501
    )
    # Source: lll
    # {  (MSTORE 3 1) (STATICCALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 64 0 64 ) (SELFDESTRUCT <contract:0x1000000000000000000000000000000000000001>) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(offset=0x3, value=0x1)
        + Op.POP(
            Op.STATICCALL(
                gas=0xC350,
                address=0x7F8A5E4DD96679590BF7CD94FC6B97C8A9C89E95,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            )
        )
        + Op.SELFDESTRUCT(address=0x7C7E7E04B71CEF12B6F4B3340E8E81E513166EC2)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x5A092B1C6583FE51BD9772742A333657BAF42C6B),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {target: Account(storage={0: 1, 1: 1})}

    state_test(env=env, pre=pre, post=post, tx=tx)
