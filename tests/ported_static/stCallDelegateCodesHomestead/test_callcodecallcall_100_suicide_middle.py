"""
Test_callcodecallcall_100_suicide_middle.

Ported from:
state_tests/stCallDelegateCodesHomestead/callcodecallcall_100_SuicideMiddleFiller.json
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
        "state_tests/stCallDelegateCodesHomestead/callcodecallcall_100_SuicideMiddleFiller.json"  # noqa: E501
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
        address=Address(0xA8B83D972811A5D75A21050DDBD5129F9787E7F2),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (DELEGATECALL 150000 <contract:0x1000000000000000000000000000000000000001> 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.DELEGATECALL(
                gas=0x249F0,
                address=0x9A0EDD7784753B55FA772622F5676FA17B14A861,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.STOP,
        balance=0xDE0B6B3A7640000,
        nonce=0,
        address=Address(0x780367237F9DC8D01B8102FE2E1625E264C3BEAC),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALL 100000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALL(
                gas=0x186A0,
                address=0x3EF59FB4DED3870B3A872C8DEE9406FC8D86C15B,
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
        address=Address(0x9A0EDD7784753B55FA772622F5676FA17B14A861),  # noqa: E501
    )
    # Source: lll
    # {  (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) [[ 2 ]] (CALL 50000 <contract:0x1000000000000000000000000000000000000003> 0 0 64 0 64 ) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SELFDESTRUCT(
            address=0x780367237F9DC8D01B8102FE2E1625E264C3BEAC
        )
        + Op.SSTORE(
            key=0x2,
            value=Op.CALL(
                gas=0xC350,
                address=0xA8B83D972811A5D75A21050DDBD5129F9787E7F2,
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
        address=Address(0x3EF59FB4DED3870B3A872C8DEE9406FC8D86C15B),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        target: Account(storage={0: 1, 1: 1}, balance=0xDE0B6B5FB6FE400),
        addr_2: Account(
            storage={},
            code=bytes.fromhex(
                "73780367237f9dc8d01b8102fe2e1625e264c3beacff6040600060406000600073a8b83d972811a5d75a21050ddbd5129f9787e7f261c350f160025500"  # noqa: E501
            ),
            balance=0,
            nonce=0,
        ),
        addr_3: Account(storage={3: 0}, balance=0x2540BE400),
        sender: Account(storage={1: 0}),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
