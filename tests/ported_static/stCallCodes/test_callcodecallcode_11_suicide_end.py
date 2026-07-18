"""
CALLCODE -> (CALLCODE -> code) selfdestruct.

Ported from:
state_tests/stCallCodes/callcodecallcode_11_SuicideEndFiller.json
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
    ["state_tests/stCallCodes/callcodecallcode_11_SuicideEndFiller.json"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.pre_alloc_mutable
def test_callcodecallcode_11_suicide_end(
    state_test: StateTestFiller,
    pre: Alloc,
) -> None:
    """CALLCODE -> (CALLCODE -> code) selfdestruct."""
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
    # {  (SSTORE 2 1) }
    addr_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x2, value=0x1) + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0xC2199DFCDDBD64567C689EA44C2D230A57651C55),  # noqa: E501
    )
    # Source: lll
    # {  [[ 0 ]] (CALLCODE 150000 <contract:0x1000000000000000000000000000000000000001> 0 0 64 0 64 ) }  # noqa: E501
    target = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.CALLCODE(
                gas=0x249F0,
                address=0x7B55D187C0E2E4EBD826F0E83B2FEBDE4EB0D92D,
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
        address=Address(0xD3A83FEFF7A026C614AAA3967807356FD83D7915),  # noqa: E501
    )
    # Source: lll
    # {  [[ 1 ]] (CALLCODE 50000 <contract:0x1000000000000000000000000000000000000002> 0 0 64 0 64 ) (SELFDESTRUCT <contract:target:0x1000000000000000000000000000000000000000>) }  # noqa: E501
    addr = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x1,
            value=Op.CALLCODE(
                gas=0xC350,
                address=0xC2199DFCDDBD64567C689EA44C2D230A57651C55,
                value=0x0,
                args_offset=0x0,
                args_size=0x40,
                ret_offset=0x0,
                ret_size=0x40,
            ),
        )
        + Op.SELFDESTRUCT(address=0xD3A83FEFF7A026C614AAA3967807356FD83D7915)
        + Op.STOP,
        balance=0x2540BE400,
        nonce=0,
        address=Address(0x7B55D187C0E2E4EBD826F0E83B2FEBDE4EB0D92D),  # noqa: E501
    )

    tx = Transaction(
        sender=sender,
        to=target,
        data=Bytes(""),
        gas_limit=3000000,
    )

    post = {
        addr: Account(storage={0: 0, 1: 0}, balance=0x2540BE400),
        addr_2: Account(storage={2: 0}, balance=0x2540BE400),
    }

    state_test(env=env, pre=pre, post=post, tx=tx)
