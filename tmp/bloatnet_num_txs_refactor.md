# BloatNet Test Refactor: Transaction Splitting Fixtures

## Problem

PR #1962 added `tx_gas_limit` support to bloatnet tests, which required calculating `num_txs` to split large transactions. This introduced repeated boilerplate across 6 test functions:

```python
# Repeated in every test function:
gas_costs = fork.gas_costs()
intrinsic_gas = fork.transaction_intrinsic_cost_calculator()(calldata=b"")
num_txs = max(1, gas_benchmark_value // tx_gas_limit)
print(f"... Number of txs: {num_txs} ...")
```

Additionally, we identified:
1. **Inconsistency**: `test_sstore_erc20_approve` accounts for `overhead_per_contract` in gas calculations, but `test_sload_empty_erc20_balanceof` doesn't (despite identical bytecode structure)
2. **Dead code**: `contracts_per_tx` is calculated in multi_opcode tests but never used functionally (only in print statements)

## Solution

Create a local `conftest.py` with shared pytest fixtures.

### New file: `tests/benchmark/stateful/bloatnet/conftest.py`

```python
"""Pytest fixtures for BloatNet benchmark tests."""

from dataclasses import dataclass

import pytest
from execution_testing import Fork
from execution_testing.common.types import GasCosts


@dataclass
class TxSplitInfo:
    """Information about how to split transactions to fit within gas limits."""

    num_txs: int
    """Number of transactions needed to fill the block."""

    gas_per_tx: int
    """Gas limit per transaction (tx_gas_limit)."""

    intrinsic_gas: int
    """Intrinsic transaction cost (21000 for empty calldata)."""

    @property
    def available_gas_per_tx(self) -> int:
        """Gas available for execution after intrinsic cost."""
        return self.gas_per_tx - self.intrinsic_gas


@pytest.fixture
def gas_costs(fork: Fork) -> GasCosts:
    """Return gas costs for the current fork."""
    return fork.gas_costs()


@pytest.fixture
def tx_split(fork: Fork, gas_benchmark_value: int, tx_gas_limit: int) -> TxSplitInfo:
    """
    Calculate transaction splitting parameters and log configuration.

    When block gas budget exceeds tx_gas_limit, we need multiple transactions
    to fill the block. This fixture calculates how many and logs the config.
    """
    intrinsic_gas = fork.transaction_intrinsic_cost_calculator()(calldata=b"")
    num_txs = max(1, gas_benchmark_value // tx_gas_limit)

    print(
        f"Block: {gas_benchmark_value / 1_000_000:.1f}M | "
        f"Tx limit: {tx_gas_limit / 1_000_000:.1f}M | "
        f"Txs: {num_txs}"
    )

    return TxSplitInfo(
        num_txs=num_txs,
        gas_per_tx=tx_gas_limit,
        intrinsic_gas=intrinsic_gas,
    )
```

### Test changes

**Before:**
```python
def test_bloatnet_balance_extcodesize(
    blockchain_test: BlockchainTestFiller,
    pre: Alloc,
    fork: Fork,
    gas_benchmark_value: int,
    tx_gas_limit: int,
    balance_first: bool,
) -> None:
    gas_costs = fork.gas_costs()
    intrinsic_gas = fork.transaction_intrinsic_cost_calculator()(calldata=b"")
    # ... cost calculations using gas_costs ...
    num_txs = max(1, gas_benchmark_value // tx_gas_limit)
    available_gas_per_tx = tx_gas_limit - intrinsic_gas - 1000
    # ...
    print(f"Tx gas limit: {tx_gas_limit / 1_000_000:.1f}M gas. Number of txs: {num_txs}. ...")
    # ...
    for _ in range(num_txs)
```

**After:**
```python
def test_bloatnet_balance_extcodesize(
    blockchain_test: BlockchainTestFiller,
    pre: Alloc,
    gas_costs: GasCosts,
    tx_split: TxSplitInfo,
    balance_first: bool,
) -> None:
    # gas_costs comes from fixture
    # tx_split.num_txs, tx_split.intrinsic_gas, tx_split.available_gas_per_tx ready to use
    # Print already happened in fixture
    # ... cost calculations using gas_costs ...
    available_gas_per_tx = tx_split.available_gas_per_tx - 1000  # test-specific reserve
    # ...
    print(f"Contracts per tx: {contracts_per_tx}. ...")  # test-specific details only
    # ...
    for _ in range(tx_split.num_txs)
```

## Changes Required

### 1. Create `bloatnet/conftest.py`
New file with `TxSplitInfo` dataclass and fixtures.

### 2. Update `test_single_opcode.py`

| Function | Changes |
|----------|---------|
| `test_sload_empty_erc20_balanceof` | Use fixtures, remove boilerplate |
| `test_sstore_erc20_approve` | Use fixtures, remove boilerplate |

### 3. Update `test_multi_opcode.py`

| Function | Changes |
|----------|---------|
| `test_bloatnet_balance_extcodesize` | Use fixtures, remove boilerplate |
| `test_bloatnet_balance_extcodecopy` | Use fixtures, remove boilerplate |
| `test_bloatnet_balance_extcodehash` | Use fixtures, remove boilerplate |
| `test_mixed_sload_sstore` | Use fixtures, remove boilerplate |

### 4. Fix SLOAD test overhead (optional, separate concern)

Add `overhead_per_contract` calculation to `test_sload_empty_erc20_balanceof` to match `test_sstore_erc20_approve`. Both have identical bytecode structure with per-contract While loops.

### 5. Clean up `contracts_per_tx` (optional, separate concern)

In multi_opcode tests, `contracts_per_tx` is calculated but only used in print statements. The actual loop count comes from the factory's `getConfig()` at runtime. Options:
- Remove calculation entirely
- Keep for documentation value with a comment explaining it's informational

## Benefits

1. **DRY**: Remove ~18 lines of repeated calculation code (3 lines x 6 tests)
2. **Centralized logging**: Consistent print format across all tests
3. **Type safety**: `TxSplitInfo` dataclass provides clear interface
4. **Maintainability**: Changes to tx splitting logic happen in one place
5. **Pytest-idiomatic**: Uses fixtures as intended by the framework

## Non-goals

- Not extracting `attack_txs` construction (test-specific bytecode makes this less valuable)
- Not extracting test-specific gas calculations (`cost_per_contract`, `loop_overhead`, etc.)
