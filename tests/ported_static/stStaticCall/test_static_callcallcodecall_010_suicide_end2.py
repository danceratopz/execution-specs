"""
Test_static_callcallcodecall_010_suicide_end2.

Ported from:
state_tests/stStaticCall/static_callcallcodecall_010_SuicideEnd2Filler.json
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
        "state_tests/stStaticCall/static_callcallcodecall_010_SuicideEnd2Filler.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.slow
@pytest.mark.pre_alloc_mutable
def test_static_callcallcodecall_010_suicide_end2(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_static_callcallcodecall_010_suicide_end2."""
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
        address=Address(0xD2AB84642B078BEF93632E4BE820382EF963CEE9),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (STATICCALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 64 0 64 ) [[ 1 ]] 1 }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.STATICCALL(
                gas=0x249F0,
                address=0xFFDB778524312FE22E1548C046D99802497877D6,
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
        address=Address(0x46165B7603E820FB916CCAA720FD052F6FEC6497),  # noqa: E501
    )
    # Source: lll
    # {  (CALLCODE 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.CALLCODE(
            gas=0x186A0,
            address=0x0B668AF06F2B7B768DBF10BFFED02BB4EFBA349D,
            value=0x0,
            args_offset=0x0,
            args_size=0x40,
            ret_offset=0x0,
            ret_size=0x40,
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xFFDB778524312FE22E1548C046D99802497877D6),  # noqa: E501
    )
    # Source: lll
    # {  (STATICCALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 64 0 64 ) (SELFDESTRUCT <contract:0x1000000000000000000000000000000000000001>) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.POP(
            Op.STATICCALL(
                gas=0xC350,
                address=0xD2AB84642B078BEF93632E4BE820382EF963CEE9,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            )
        )
        + Op.SELFDESTRUCT(address=0xFFDB778524312FE22E1548C046D99802497877D6)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x0B668AF06F2B7B768DBF10BFFED02BB4EFBA349D),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        target: Account(storage={0: 1, 1: 1}),
        addr_3: Account(storage={3: 0}, balance=0x2540BE400),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
