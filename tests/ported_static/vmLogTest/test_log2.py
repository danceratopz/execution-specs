"""
Ori Pomerantz qbzzt1@gmail.com.

Ported from:
state_tests/VMTests/vmLogTest/log2Filler.yml
"""

import pytest
from execution_testing import (
    Account,
    Address,
    Alloc,
    Bytes,
    Environment,
    Hash,
    StateTestFiller,
    Transaction,
)
from execution_testing.forks import Fork
from execution_testing.specs.static_state.expect_section import (
    resolve_expect_post,
)
from execution_testing.vm import Op

REFERENCE_SPEC_GIT_PATH = "N/A"
REFERENCE_SPEC_VERSION = "N/A"


@pytest.mark.ported_from(
    ["state_tests/VMTests/vmLogTest/log2Filler.yml"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.parametrize(
    "d, g, v",
    [
        pytest.param(
            0,
            0,
            0,
            id="emptyMem",
        ),
        pytest.param(
            1,
            0,
            0,
            id="memStartTooHigh",
        ),
        pytest.param(
            2,
            0,
            0,
            id="memSizeTooHigh",
        ),
        pytest.param(
            3,
            0,
            0,
            id="memSizeZero",
        ),
        pytest.param(
            4,
            0,
            0,
            id="nonEmptyMem",
        ),
        pytest.param(
            5,
            0,
            0,
            id="log_0_1",
        ),
        pytest.param(
            6,
            0,
            0,
            id="log_31_1",
        ),
        pytest.param(
            7,
            0,
            0,
            id="caller",
        ),
        pytest.param(
            8,
            0,
            0,
            id="maxTopic",
        ),
    ],
)
@pytest.mark.pre_alloc_mutable
def test_log2(
    state_test: StateTestFiller,
    pre: Alloc,
    fork: Fork,
    d: int,
    g: int,
    v: int,
) -> None:
    """Ori Pomerantz qbzzt1@gmail."""
    coinbase = Address(0x2ADC25665018AA1FE0E6BC666DAC8FC2697FF9BA)
    contract_0 = Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0EB)
    contract_1 = Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0EC)
    contract_2 = Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0ED)
    contract_3 = Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0EE)
    contract_4 = Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0EF)
    contract_5 = Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0F0)
    contract_6 = Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0F1)
    contract_7 = Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0F2)
    contract_8 = Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0F3)
    contract_9 = Address(0x591FDD8FC52764C042526D9897E05273671EBC60)
    sender = pre.fund_eoa(amount=0x100000000000)

    env = Environment(
        fee_recipient=coinbase,
        number=1,
        timestamp=1000,
        prev_randao=0x20000,
        base_fee_per_gas=10,
        gas_limit=100000000,
    )

    # Source: lll
    # {   ; emptyMem
    #     (log2 0 0 0 0)
    #
    #     [[0]] 0x600D
    # }
    contract_0 = pre.deploy_contract(  # noqa: F841
        code=Op.LOG2(offset=0x0, size=0x0, topic_1=0x0, topic_2=0x0)
        + Op.SSTORE(key=0x0, value=0x600D)
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0EB),  # noqa: E501
    )
    # Source: lll
    # {      ; memStartTooHigh
    #    (def 'neg1 (- 0 1))
    #
    #    [0]   0xaabbffffffffffffffffffffffffffffffffffffffffffffffffffffffffccdd  # noqa: E501
    #    (log2 neg1 1 0 0)
    #    [[0]] 0x600D
    # }
    contract_1 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(
            offset=0x0,
            value=0xAABBFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFCCDD,  # noqa: E501
        )
        + Op.LOG2(offset=Op.SUB(0x0, 0x1), size=0x1, topic_1=0x0, topic_2=0x0)
        + Op.SSTORE(key=0x0, value=0x600D)
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0EC),  # noqa: E501
    )
    # Source: lll
    # {        ; memSizeTooHigh
    #    (def 'neg1 (- 0 1))
    #
    #    [0] 0xaabbffffffffffffffffffffffffffffffffffffffffffffffffffffffffccdd
    #    (log2 1 neg1 0 0)
    #    [[0]] 0x600D
    # }
    contract_2 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(
            offset=0x0,
            value=0xAABBFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFCCDD,  # noqa: E501
        )
        + Op.LOG2(offset=0x1, size=Op.SUB(0x0, 0x1), topic_1=0x0, topic_2=0x0)
        + Op.SSTORE(key=0x0, value=0x600D)
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0ED),  # noqa: E501
    )
    # Source: lll
    # {        ; memSizeZero
    #    [0] 0xaabbffffffffffffffffffffffffffffffffffffffffffffffffffffffffccdd
    #    (log2 1 0 0 0)
    #    [[0]] 0x600D
    # }
    contract_3 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(
            offset=0x0,
            value=0xAABBFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFCCDD,  # noqa: E501
        )
        + Op.LOG2(offset=0x1, size=0x0, topic_1=0x0, topic_2=0x0)
        + Op.SSTORE(key=0x0, value=0x600D)
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0EE),  # noqa: E501
    )
    # Source: lll
    # {        ; nonEmptyMem
    #    [0] 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    #    (log2 0 32 0 0)
    #    [[0]] 0x600D
    # }
    contract_4 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(
            offset=0x0,
            value=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,  # noqa: E501
        )
        + Op.LOG2(offset=0x0, size=0x20, topic_1=0x0, topic_2=0x0)
        + Op.SSTORE(key=0x0, value=0x600D)
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0EF),  # noqa: E501
    )
    # Source: lll
    # {        ; log_0_1
    #    [0] 0xaabbffffffffffffffffffffffffffffffffffffffffffffffffffffffffccdd
    #    (log2 0 1 0 0)
    #    [[0]] 0x600D
    # }
    contract_5 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(
            offset=0x0,
            value=0xAABBFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFCCDD,  # noqa: E501
        )
        + Op.LOG2(offset=0x0, size=0x1, topic_1=0x0, topic_2=0x0)
        + Op.SSTORE(key=0x0, value=0x600D)
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0F0),  # noqa: E501
    )
    # Source: lll
    # {        ; log_31_1
    #    [0] 0xaabbffffffffffffffffffffffffffffffffffffffffffffffffffffffffccdd
    #    (log2 31 1 0 0)
    #    [[0]] 0x600D
    # }
    contract_6 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(
            offset=0x0,
            value=0xAABBFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFCCDD,  # noqa: E501
        )
        + Op.LOG2(offset=0x1F, size=0x1, topic_1=0x0, topic_2=0x0)
        + Op.SSTORE(key=0x0, value=0x600D)
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0F1),  # noqa: E501
    )
    # Source: lll
    # {        ; caller (as topic)
    #    [0] 0xaabbffffffffffffffffffffffffffffffffffffffffffffffffffffffffccdd
    #    (log2 0 32 0 (caller))
    #    [[0]] 0x600D
    # }
    contract_7 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE(
            offset=0x0,
            value=0xAABBFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFCCDD,  # noqa: E501
        )
        + Op.LOG2(offset=0x0, size=0x20, topic_1=0x0, topic_2=Op.CALLER)
        + Op.SSTORE(key=0x0, value=0x600D)
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0F2),  # noqa: E501
    )
    # Source: lll
    # {        ; maxTopic
    #    (def 'neg1 (- 0 1))
    #
    #    (mstore8 0 0xFF)
    #    (log2 31 1 neg1 neg1)
    #    [[0]] 0x600D
    # }
    contract_8 = pre.deploy_contract(  # noqa: F841
        code=Op.MSTORE8(offset=0x0, value=0xFF)
        + Op.LOG2(
            offset=0x1F,
            size=0x1,
            topic_1=Op.SUB(0x0, 0x1),
            topic_2=Op.SUB(0x0, 0x1),
        )
        + Op.SSTORE(key=0x0, value=0x600D)
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0F3),  # noqa: E501
    )
    # Source: lll
    # {
    #     (delegatecall (gas) (+ 0x1000 $4) 0 0 0 0)
    # }
    contract_9 = pre.deploy_contract(  # noqa: F841
        code=Op.DELEGATECALL(
            gas=Op.GAS,
            address=Op.ADD(
                0x3D3A89ACB8CDB2F9522DCBB178275DBB58C5E0EB,
                Op.CALLDATALOAD(offset=0x4),
            ),
            args_offset=0x0,
            args_size=0x0,
            ret_offset=0x0,
            ret_size=0x0,
        )
        + Op.STOP,
        storage={0: 2989},
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x591FDD8FC52764C042526D9897E05273671EBC60),  # noqa: E501
    )

    expect_entries_: list[dict] = [
        {
            "indexes": {"data": [0, 3, 4, 5, 6, 7, 8], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {contract_9: Account(storage={0: 24589})},
        },
        {
            "indexes": {"data": [1, 2], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {contract_9: Account(storage={0: 2989})},
        },
    ]

    post, _exc = resolve_expect_post(expect_entries_, d, g, v, fork)

    tx_data = [
        Bytes("693c6139") + Hash(0x0),
        Bytes("693c6139") + Hash(0x1),
        Bytes("693c6139") + Hash(0x2),
        Bytes("693c6139") + Hash(0x3),
        Bytes("693c6139") + Hash(0x4),
        Bytes("693c6139") + Hash(0x5),
        Bytes("693c6139") + Hash(0x6),
        Bytes("693c6139") + Hash(0x7),
        Bytes("693c6139") + Hash(0x8),
    ]
    tx_gas = [16777216]
    tx_value = [1]

    tx = Transaction(
        sender=sender,
        to=contract_9,
        data=tx_data[d],
        gas_limit=tx_gas[g],
        value=tx_value[v],
        error=_exc,
    )

    state_test(env=env, pre=pre, post=post, tx=tx)
