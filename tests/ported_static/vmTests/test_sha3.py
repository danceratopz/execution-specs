"""
Ori Pomerantz qbzzt1@gmail.com.

Ported from:
state_tests/VMTests/vmTests/sha3Filler.yml
"""

import pytest
from execution_testing import (
    EOA,
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
    ["state_tests/VMTests/vmTests/sha3Filler.yml"],
)
@pytest.mark.valid_from("Cancun")
@pytest.mark.parametrize(
    "d, g, v",
    [
        pytest.param(
            0,
            0,
            0,
            id="sha3_nodata",
        ),
        pytest.param(
            1,
            0,
            0,
            id="sha3_five_0s",
        ),
        pytest.param(
            2,
            0,
            0,
            id="sha3_ten_0s",
        ),
        pytest.param(
            3,
            0,
            0,
            id="sha3_0xFFFFF_0s",
        ),
        pytest.param(
            4,
            0,
            0,
            id="sha3_highmem",
        ),
        pytest.param(
            5,
            0,
            0,
            id="sha3_huge_buffer",
        ),
        pytest.param(
            6,
            0,
            0,
            id="sha3_neg1_neg1",
        ),
        pytest.param(
            7,
            0,
            0,
            id="sha3_neg1_2",
        ),
        pytest.param(
            8,
            0,
            0,
            id="sha3_0x1000000_2",
        ),
        pytest.param(
            9,
            0,
            0,
            id="sha3_960_1",
        ),
        pytest.param(
            10,
            0,
            0,
            id="sha3_992_1",
        ),
        pytest.param(
            11,
            0,
            0,
            id="sha3_1024_1",
        ),
        pytest.param(
            12,
            0,
            0,
            id="sha3_1984_1",
        ),
        pytest.param(
            13,
            0,
            0,
            id="sha3_2016_1",
        ),
        pytest.param(
            14,
            0,
            0,
            id="sha3_2016_32",
        ),
        pytest.param(
            15,
            0,
            0,
            id="sha3_2048_1",
        ),
        pytest.param(
            16,
            0,
            0,
            id="sha3_1024_0",
        ),
    ],
)
@pytest.mark.pre_alloc_mutable
def test_sha3(
    state_test: StateTestFiller,
    pre: Alloc,
    fork: Fork,
    d: int,
    g: int,
    v: int,
) -> None:
    """Ori Pomerantz qbzzt1@gmail."""
    coinbase = Address(0x2ADC25665018AA1FE0E6BC666DAC8FC2697FF9BA)
    contract_0 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F27F)
    contract_1 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F280)
    contract_2 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F281)
    contract_3 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F282)
    contract_4 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F283)
    contract_5 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F284)
    contract_6 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F285)
    contract_7 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F286)
    contract_8 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F287)
    contract_9 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F288)
    contract_10 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F289)
    contract_11 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28A)
    contract_12 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28B)
    contract_13 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28C)
    contract_14 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28D)
    contract_15 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28E)
    contract_16 = Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28F)
    contract_17 = Address(0xE968019D3D5887782166C148AE15276F722BBD3D)
    sender = EOA(
        key=0x45A915E4D060149EB4365960E6A7A45F334393093061116B197E3240065FF2D8
    )

    env = Environment(
        fee_recipient=coinbase,
        number=1,
        timestamp=1000,
        prev_randao=0x20000,
        base_fee_per_gas=10,
        gas_limit=100000000,
    )

    pre[sender] = Account(balance=0x100000000000)
    # Source: lll
    # {
    #     [[0]] (sha3 0 0)
    # }
    contract_0 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x0, size=0x0)) + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F27F),  # noqa: E501
    )
    # Source: lll
    # {
    #     [[0]] (sha3 4 5)
    # }
    contract_1 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x4, size=0x5)) + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F280),  # noqa: E501
    )
    # Source: lll
    # {
    #     [[0]] (sha3 10 10)
    # }
    contract_2 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0xA, size=0xA)) + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F281),  # noqa: E501
    )
    # Source: lll
    # {
    #     [[0]] (sha3 1000 0xFFFFF)
    # }
    contract_3 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x3E8, size=0xFFFFF))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F282),  # noqa: E501
    )
    # Source: lll
    # {
    #     ; The result here is zero, because we run out of gas
    #     [[0]] (sha3 0xfffffffff  100)
    # }
    contract_4 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0xFFFFFFFFF, size=0x64))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F283),  # noqa: E501
    )
    # Source: lll
    # {
    #     ; The result here is zero, because we run out of gas
    #     [[0]] (sha3 10000 0xfffffffff)
    # }
    contract_5 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x2710, size=0xFFFFFFFFF))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F284),  # noqa: E501
    )
    # Source: lll
    # {
    #     (def 'neg1 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)  # noqa: E501
    #     [[0]] (sha3 neg1 neg1)
    # }
    contract_6 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.SHA3(
                offset=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,  # noqa: E501
                size=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,  # noqa: E501
            ),
        )
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F285),  # noqa: E501
    )
    # Source: lll
    # {
    #     (def 'neg1 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)  # noqa: E501
    #     [[0]] (sha3 neg1 2)
    # }
    contract_7 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(
            key=0x0,
            value=Op.SHA3(
                offset=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,  # noqa: E501
                size=0x2,
            ),
        )
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F286),  # noqa: E501
    )
    # Source: lll
    # {
    #     [[0]] (sha3 0x1000000 2)
    # }
    contract_8 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x1000000, size=0x2))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F287),  # noqa: E501
    )
    # Source: lll
    # {
    #   [[ 0 ]] (sha3 960 1)
    # }
    contract_9 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x3C0, size=0x1))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F288),  # noqa: E501
    )
    # Source: lll
    # {
    #   [[ 0 ]] (sha3 992 1)
    # }
    contract_10 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x3E0, size=0x1))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F289),  # noqa: E501
    )
    # Source: lll
    # {
    #   [[ 0 ]] (sha3 1024 1)
    # }
    contract_11 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x400, size=0x1))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28A),  # noqa: E501
    )
    # Source: lll
    # {
    #   [[ 0 ]] (sha3 1984 1)
    # }
    contract_12 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x7C0, size=0x1))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28B),  # noqa: E501
    )
    # Source: lll
    # {
    #   [[ 0 ]] (sha3 2016 1)
    # }
    contract_13 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x7E0, size=0x1))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28C),  # noqa: E501
    )
    # Source: lll
    # {
    #   [[ 0 ]] (sha3 2048 1)
    # }
    contract_14 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x800, size=0x1))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28D),  # noqa: E501
    )
    # Source: lll
    # {
    #   [[ 0 ]] (sha3 1024 0)
    # }
    contract_15 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x400, size=0x0))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28E),  # noqa: E501
    )
    # Source: lll
    # {
    #   [[ 0 ]] (sha3 2016 32)
    # }
    contract_16 = pre.deploy_contract(  # noqa: F841
        code=Op.SSTORE(key=0x0, value=Op.SHA3(offset=0x7E0, size=0x20))
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0x9BD31017C4B5F9FDC274F8885FC63391F506F28F),  # noqa: E501
    )
    # Source: lll
    # {
    #     (call (- 0 1) (+ 0x1000 $4) 0
    #        0x0F 0x10   ; arg offset and length to get the 0x1234...f0 value
    #        0x20 0x40)  ; return offset and length
    # }
    contract_17 = pre.deploy_contract(  # noqa: F841
        code=Op.CALL(
            gas=Op.SUB(0x0, 0x1),
            address=Op.ADD(
                0x9BD31017C4B5F9FDC274F8885FC63391F506F27F,
                Op.CALLDATALOAD(offset=0x4),
            ),
            value=0x0,
            args_offset=0xF,
            args_size=0x10,
            ret_offset=0x20,
            ret_size=0x40,
        )
        + Op.STOP,
        balance=0xBA1A9CE0BA1A9CE,
        nonce=0,
        address=Address(0xE968019D3D5887782166C148AE15276F722BBD3D),  # noqa: E501
    )

    expect_entries_: list[dict] = [
        {
            "indexes": {"data": [0], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_0: Account(
                    storage={
                        0: 0xC5D2460186F7233C927E7DB2DCC703C0E500B653CA82273B7BFAD8045D85A470,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [1], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_1: Account(
                    storage={
                        0: 0xC41589E7559804EA4A2080DAD19D876A024CCB05117835447D72CE08C1D020EC,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [2], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_2: Account(
                    storage={
                        0: 0x6BD2DD6BD408CBEE33429358BF24FDC64612FBF8B1B4DB604518F40FFD34B607,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [3], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_3: Account(
                    storage={
                        0: 0xBE6F1B42B34644F918560A07F959D23E532DEA5338E4B9F63DB0CAEB608018FA,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [4], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {contract_4: Account(storage={0: 0})},
        },
        {
            "indexes": {"data": [5], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {contract_5: Account(storage={0: 0})},
        },
        {
            "indexes": {"data": [6], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {contract_6: Account(storage={0: 0})},
        },
        {
            "indexes": {"data": [7], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {contract_7: Account(storage={0: 0})},
        },
        {
            "indexes": {"data": [8], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {contract_8: Account(storage={0: 0})},
        },
        {
            "indexes": {"data": [9], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_9: Account(
                    storage={
                        0: 0xBC36789E7A1E281436464229828F817D6612F7B477D66591FF96A9E064BCC98A,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [10], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_10: Account(
                    storage={
                        0: 0xBC36789E7A1E281436464229828F817D6612F7B477D66591FF96A9E064BCC98A,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [11], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_11: Account(
                    storage={
                        0: 0xBC36789E7A1E281436464229828F817D6612F7B477D66591FF96A9E064BCC98A,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [12], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_12: Account(
                    storage={
                        0: 0xBC36789E7A1E281436464229828F817D6612F7B477D66591FF96A9E064BCC98A,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [13], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_13: Account(
                    storage={
                        0: 0xBC36789E7A1E281436464229828F817D6612F7B477D66591FF96A9E064BCC98A,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [15], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_14: Account(
                    storage={
                        0: 0xBC36789E7A1E281436464229828F817D6612F7B477D66591FF96A9E064BCC98A,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [16], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_15: Account(
                    storage={
                        0: 0xC5D2460186F7233C927E7DB2DCC703C0E500B653CA82273B7BFAD8045D85A470,  # noqa: E501
                    },
                ),
            },
        },
        {
            "indexes": {"data": [14], "gas": -1, "value": -1},
            "network": [">=Cancun"],
            "result": {
                contract_16: Account(
                    storage={
                        0: 0x290DECD9548B62A8D60345A988386FC84BA6BC95484008F6362F93160EF3E563,  # noqa: E501
                    },
                ),
            },
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
        Bytes("693c6139") + Hash(0x9),
        Bytes("693c6139") + Hash(0xA),
        Bytes("693c6139") + Hash(0xB),
        Bytes("693c6139") + Hash(0xC),
        Bytes("693c6139") + Hash(0xD),
        Bytes("693c6139") + Hash(0x10),
        Bytes("693c6139") + Hash(0xE),
        Bytes("693c6139") + Hash(0xF),
    ]
    tx_gas = [16777216]
    tx_value = [1]

    tx = Transaction(
        sender=sender,
        to=contract_17,
        data=tx_data[d],
        gas_limit=tx_gas[g],
        value=tx_value[v],
        error=_exc,
    )

    state_test(env=env, pre=pre, post=post, tx=tx)
