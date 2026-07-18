"""
Test_static_callcallcodecallcode_011_suicide_end.

Ported from:
state_tests/stStaticCall/static_callcallcodecallcode_011_SuicideEndFiller.json
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
        "state_tests/stStaticCall/static_callcallcodecallcode_011_SuicideEndFiller.json"  # noqa: E501
    ],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.slow
@pytest.mark.pre_alloc_mutable
def test_static_callcallcodecallcode_011_suicide_end(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """Test_static_callcallcodecallcode_011_suicide_end."""
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
        address=Address(0x3B0F15F0901855E9AC57D75CE7DA6BD04E6879A9),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (STATICCALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 64 0 64 ) [[ 1 ]] 1 }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.STATICCALL(
                gas=0x249F0,
                address=0xAF4DB9E330B476A8C005A630F574A9D9DD336982,
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
        address=Address(0xBE0E2EFC6019A7675DF7A30748BEEC6D57EBB82F),  # noqa: E501
    )
    # Source: lll
    # {  (DELEGATECALL 100000 <contract:0x1000000000000000000000000000000000000002> 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.DELEGATECALL(
            gas=0x186A0,
            address=0xB617EF074583E07F747055123761D92E80A2979C,
            args_offset=0x0,
            args_size=0x40,
            ret_offset=0x0,
            ret_size=0x40,
        )
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xAF4DB9E330B476A8C005A630F574A9D9DD336982),  # noqa: E501
    )
    # Source: lll
    # {  (DELEGATECALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 64 0 64 ) (SELFDESTRUCT <contract:0x1000000000000000000000000000000000000001>) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.POP(
            Op.DELEGATECALL(
                gas=0xC350,
                address=0x3B0F15F0901855E9AC57D75CE7DA6BD04E6879A9,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            )
        )
        + Op.SELFDESTRUCT(address=0xAF4DB9E330B476A8C005A630F574A9D9DD336982)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xB617EF074583E07F747055123761D92E80A2979C),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        target: Account(storage={0: 1, 1: 1}),
        addr_2: Account(balance=0x2540BE400),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
