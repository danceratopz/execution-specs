"""
Test_static_callcodecallcodecall_110_suicide_middle2.

Ported from:
state_tests/stStaticCall/static_callcodecallcodecall_110_SuicideMiddle2Filler.json
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
        "state_tests/stStaticCall/static_callcodecallcodecall_110_SuicideMiddle2Filler.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.slow
@pytest.mark.pre_alloc_mutable
def test_static_callcodecallcodecall_110_suicide_middle2(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_static_callcodecallcodecall_110_suicide_middle2."""
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
        address=Address(0xA464D2E5168CBCF97B5816CFE131AB6CDBFD08C9),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALLCODE 150000 <contract:0x1000000000000000000000000000000000000001> (CALLVALUE) 0 64 0 64 ) [[ 1 ]] (GAS) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALLCODE(
                gas=0x249F0,
                address=0x3F723C230B47CCEC199B4ED6F005BB66289E6930,
                value=Op.CALLVALUE,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.SSTORE(key=0x1, value=Op.GAS)
        + Op.STOP,
        balance=0xDE0B6B3A7640000,
        nonce=0,
        address=Address(0x2179C84EE37E7018357DDC548A4B98B2506BD76A),  # noqa: E501
    )
    # Source: lll
    # {  (CALLCODE 100000 <contract:0x1000000000000000000000000000000000000002> (CALLVALUE) 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.CALLCODE(
            gas=0x186A0,
            address=0xAE48A9868BA7C9F395F24C437F365DC74989E9F4,
            value=Op.CALLVALUE,
            args_offset=0x0,
            args_size=0x40,
            ret_offset=0x0,
            ret_size=0x40,
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x3F723C230B47CCEC199B4ED6F005BB66289E6930),  # noqa: E501
    )
    # Source: lll
    # {  (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) (STATICCALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 64 0 64 ) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SELFDESTRUCT(
            address=0x2179C84EE37E7018357DDC548A4B98B2506BD76A
        )
        + Op.STATICCALL(
            gas=0xC350,
            address=0xA464D2E5168CBCF97B5816CFE131AB6CDBFD08C9,
            args_offset=0x0,
            args_size=0x40,
            ret_offset=0x0,
            ret_size=0x40,
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xAE48A9868BA7C9F395F24C437F365DC74989E9F4),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {target: Account(balance=0xDE0B6B3A7640000)}

    state_test(env=env, pre=pre, post=post, tx=tx)
