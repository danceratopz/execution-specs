"""
CALLCODE -> CALL <-> CALLCODE.

Ported from:
state_tests/stCallCodes/callcodecallcallcode_ABCB_RECURSIVEFiller.json
"""

import pytest
from execution_testing import (
    Account,
    Address,
    Alloc,
    Bytes,
    Environment,
    Fork,
    StateTestFiller,
    Transaction,
)
from execution_testing.forks import Amsterdam
from execution_testing.vm import Op

REFERENCE_SPEC_GIT_PATH = "N/A"
REFERENCE_SPEC_VERSION = "N/A"


@pytest.mark.ported_from(
    ["state_tests/stCallCodes/callcodecallcallcode_ABCB_RECURSIVEFiller.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcodecallcallcode_abcb_recursive(
    state_test: StateTestFiller,
    fork: Fork,
    pre: Alloc,
) -> None:
    """CALLCODE -> CALL <-> CALLCODE."""
    coinbase = Address(0x2ADC25665018AA1FE0E6BC666DAC8FC2697FF9BA)
    sender = pre.fund_eoa(amount=0xDE0B6B3A7640000)

    env = Environment(
        fee_recipient=coinbase,
        number=1,
        timestamp=1000,
        prev_randao=0x20000,
        base_fee_per_gas=10,
    )

    # Source: lll
    # {  [[ 0 ]] (CALLCODE 25000000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALLCODE(
                gas=0x17D7840,
                address=0xB98CAF407E576C51730DBB30FF9A28080A1F8EA3,
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
        address=Address(0x790EC2F1021BF1D19608F0F8BD74627AC1332B10),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALL 1000000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALL(
                gas=0xF4240,
                address=0xFCE753C1CF238278FC05DB635E4325F147CE87BE,
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
        address=Address(0xB98CAF407E576C51730DBB30FF9A28080A1F8EA3),  # noqa: E501
    )
    # Source: lll
    # {  [[ 2 ]] (CALLCODE 500000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x2,
            value=Op.CALLCODE(
                gas=0x7A120,
                address=0xB98CAF407E576C51730DBB30FF9A28080A1F8EA3,
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
        address=Address(0xFCE753C1CF238278FC05DB635E4325F147CE87BE),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=2600000 if fork >= Amsterdam else 600000,
    )

    post = {
        target: Account(storage={0: 1, 1: 1}),
        addr: Account(storage={1: 0, 2: 0}),
        addr_2: Account(
            storage={
                1: 0,
                2: 0,
            }
        ),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
