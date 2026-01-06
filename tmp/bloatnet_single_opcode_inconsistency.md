# Gas Calculation Inconsistency: SLOAD vs SSTORE Tests

## Summary

`test_sload_empty_erc20_balanceof` and `test_sstore_erc20_approve` in `test_single_opcode.py` have identical bytecode structures but inconsistent gas overhead accounting.

## The Inconsistency

### SSTORE test (correct)

Separates one-time and per-iteration costs:

```python
# Per-contract one-time overhead (setup + teardown)
overhead_per_contract = (
    gas_costs.G_VERY_LOW  # MSTORE init counter (3)
    + 15  # Memory expansion
    + gas_costs.G_JUMPDEST  # Loop start (1)
    + gas_costs.G_LOW  # MLOAD condition (5)
    + gas_costs.G_BASE * 2  # ISZERO * 2 (4)
    + gas_costs.G_MID  # JUMPI (8)
    + gas_costs.G_BASE  # POP cleanup (2)
)  # = 38 gas/contract

# Per-iteration overhead
loop_overhead = (...)  # = 44 gas/iteration

# Calculation accounts for both
total_overhead_per_tx = intrinsic_gas + (overhead_per_contract * num_contracts)
available_gas_per_tx = tx_gas_limit - total_overhead_per_tx
```

### SLOAD test (missing overhead)

Only accounts for per-iteration costs:

```python
# Per-iteration overhead only - NO per-contract overhead defined
loop_overhead = (...)  # = 41 gas/iteration

# Calculation missing overhead_per_contract
available_gas_per_tx = tx_gas_limit - intrinsic_gas  # Missing: - (overhead_per_contract * num_contracts)
```

## Impact

With `num_contracts=100`, the SLOAD test doesn't account for:
- ~38 gas × 100 contracts = **~3,800 gas unaccounted per transaction**

This means `calls_per_contract` is slightly overestimated in the SLOAD test.

## Root Cause

No structure enforcing separation of:
1. **Per-contract one-time costs** - loop setup/teardown (counter init, memory expansion, JUMPDEST, cleanup)
2. **Per-iteration costs** - loop body operations

## Proposed Fix

Introduce a `LoopGasModel` dataclass that makes both components required:

```python
@dataclass
class LoopGasModel:
    """Gas model for benchmark attack loops."""

    overhead_per_contract: int
    """One-time cost per contract: counter init, memory expansion, JUMPDEST, cleanup."""

    cost_per_iteration: int
    """Per-iteration cost: loop body operations + condition check."""

    cold_warm_diff: int
    """Extra cost for first call vs subsequent (G_COLD - G_WARM)."""

    def calls_per_contract(
        self,
        available_gas: int,
        num_contracts: int,
    ) -> int:
        """Calculate how many calls fit per contract given available gas."""
        total_overhead = self.overhead_per_contract * num_contracts
        per_contract = (available_gas - total_overhead) // num_contracts
        return int((per_contract - self.cold_warm_diff) // self.cost_per_iteration)
```

**Benefits:**
- Can't forget `overhead_per_contract` - it's a required field
- Centralizes the calculation logic
- Self-documenting: field names explain what each component represents
- Testable: the calculation can be unit tested independently

**Usage:**
```python
gas_model = LoopGasModel(
    overhead_per_contract=38,  # Required - can't omit!
    cost_per_iteration=loop_overhead + gas_costs.G_WARM_ACCOUNT_ACCESS + erc20_internal_gas,
    cold_warm_diff=gas_costs.G_COLD_ACCOUNT_ACCESS - gas_costs.G_WARM_ACCOUNT_ACCESS,
)

calls_per_contract = gas_model.calls_per_contract(
    available_gas=tx_split.available_gas_per_tx,
    num_contracts=num_contracts,
)
```

## Recommendation

1. **Immediate fix**: Add `overhead_per_contract` calculation to SLOAD test to match SSTORE
2. **Structural fix**: Consider introducing `LoopGasModel` to prevent future inconsistencies

The structural fix may be overkill for just 2 tests, but could be valuable if more single-opcode benchmarks are added.
