"""
CALLCODE -> CALLCODE -> (suicide) CALL -> code.

Ported from:
state_tests/stCallCodes/callcodecallcodecall_110_SuicideMiddleFiller.json
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
        "state_tests/stCallCodes/callcodecallcodecall_110_SuicideMiddleFiller.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcodecallcodecall_110_suicide_middle(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """CALLCODE -> CALLCODE -> (suicide) CALL -> code."""
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
        address=Address(0xCC3DCD08DE86270729FE819D7248EF26B118CE47),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALLCODE 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALLCODE(
                gas=0x249F0,
                address=0xA5E35DECE9D1BBB682970EAD5771167B4EE5E1B3,
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
        address=Address(0x0DF161B4439D3B792110DBF41F5DE6F6B695DF5B),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALLCODE 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALLCODE(
                gas=0x186A0,
                address=0xB107F9CBF1BAC0603BA33FDCE212F589F29F5926,
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
        address=Address(0xA5E35DECE9D1BBB682970EAD5771167B4EE5E1B3),  # noqa: E501
    )
    # Source: lll
    # {  (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) [[ 2 ]] (CALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 0 64 0 64 ) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SELFDESTRUCT(
            address=0x0DF161B4439D3B792110DBF41F5DE6F6B695DF5B
        )
        + Op.SSTORE(
            key=0x2,
            value=Op.CALL(
                gas=0xC350,
                address=0xCC3DCD08DE86270729FE819D7248EF26B118CE47,
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
        address=Address(0xB107F9CBF1BAC0603BA33FDCE212F589F29F5926),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        addr: Account(storage={0: 0, 1: 0, 2: 0}, balance=0x2540BE400),
        addr_2: Account(storage={3: 0}, balance=0x2540BE400),
        addr_3: Account(storage={3: 0}, balance=0x2540BE400),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
