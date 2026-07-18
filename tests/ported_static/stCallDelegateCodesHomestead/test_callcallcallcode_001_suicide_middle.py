"""
Test_callcallcallcode_001_suicide_middle.

Ported from:
state_tests/stCallDelegateCodesHomestead/callcallcallcode_001_SuicideMiddleFiller.json
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
        "state_tests/stCallDelegateCodesHomestead/callcallcallcode_001_SuicideMiddleFiller.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcallcallcode_001_suicide_middle(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_callcallcallcode_001_suicide_middle."""
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
        address=Address(0x94F5D118B791104AA26AD49E4145509B2B274E99),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALL(
                gas=0x249F0,
                address=0x478CD85B680DD9C107BE535A13ABAEC2CA7670EE,
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
        address=Address(0x7F315C357F3B35910E6E2BCFB553B537002C95AA),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALL 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALL(
                gas=0x186A0,
                address=0x7C0ADBBA08E08D9754E0E70B52AEFE2948DB2CCB,
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
        address=Address(0x478CD85B680DD9C107BE535A13ABAEC2CA7670EE),  # noqa: E501
    )
    # Source: lll
    # {  (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) [[ 2 ]] (DELEGATECALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 64 0 64 ) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SELFDESTRUCT(
            address=0x7F315C357F3B35910E6E2BCFB553B537002C95AA
        )
        + Op.SSTORE(
            key=0x2,
            value=Op.DELEGATECALL(
                gas=0xC350,
                address=0x94F5D118B791104AA26AD49E4145509B2B274E99,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x7C0ADBBA08E08D9754E0E70B52AEFE2948DB2CCB),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        addr_2: Account(
            storage={},
            code=bytes.fromhex(
                "737f315c357f3b35910e6e2bcfb553b537002c95aaff60406000604060007394f5d118b791104aa26ad49e4145509b2b274e9961c350f460025500"  # noqa: E501
            ),
            balance=0,
            nonce=0,
        ),
        target: Account(storage={0: 1}, balance=0xDE0B6B5FB6FE400),
        addr: Account(storage={1: 1, 2: 0}, balance=0x2540BE400),
        addr_3: Account(storage={2: 0, 3: 0}, balance=0x2540BE400),
        sender: Account(storage={2: 0, 3: 0}),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
