# Cold-Access Split Strategy for Benchmark Tests

## Problem Statement

When benchmarking cold storage/account access across multiple transactions, the current transaction splitting approach creates **identical transactions**. This defeats the purpose of cold-access benchmarks:

```
Current behavior (identical txs):
┌─────────────────────────────────────────────────────────────┐
│ Tx 1: Access contracts 0-999    → all COLD (2600 gas each) │
│ Tx 2: Access contracts 0-999    → all WARM (100 gas each)  │ ← Wrong!
│ Tx 3: Access contracts 0-999    → all WARM (100 gas each)  │ ← Wrong!
└─────────────────────────────────────────────────────────────┘

Desired behavior (offset-based txs):
┌─────────────────────────────────────────────────────────────┐
│ Tx 1: Access contracts 0-999    → all COLD (2600 gas each) │
│ Tx 2: Access contracts 1000-1999 → all COLD                │ ← Correct!
│ Tx 3: Access contracts 2000-2999 → all COLD                │ ← Correct!
└─────────────────────────────────────────────────────────────┘
```

This issue affects any benchmark that:
1. Needs multiple transactions due to `tx_gas_limit` caps (e.g., Fusaka's 16M limit)
2. Measures cold access patterns (BALANCE, EXTCODESIZE, SLOAD on new slots, etc.)

## Current State

### `BenchmarkTest.split_transaction` (benchmark.py:374-402)

```python
def split_transaction(
    self, tx: Transaction, gas_limit_cap: int | None
) -> List[Transaction]:
    """Split a transaction that exceeds the gas limit cap into multiple transactions."""
    ...
    for i in range(num_splits):
        split_tx = tx.model_copy()
        split_tx.gas_limit = HexNumber(...)
        split_tx.nonce = HexNumber(tx.nonce + i)
        # NOTE: calldata is identical across all splits
        split_transactions.append(split_tx)
    return split_transactions
```

**What it handles:**
- Calculating number of splits based on gas
- Copying the transaction
- Adjusting `gas_limit` (last tx gets remainder)
- Incrementing `nonce`

**What it doesn't handle:**
- Per-transaction calldata with offset information
- Coordination with bytecode that reads the offset

### Bloatnet Attack Pattern

Current bloatnet tests use CREATE2 address generation:

```python
# Loops from salt=0 to salt=num_contracts (hardcoded)
While(
    body=(
        Op.SHA3(11, 85)  # keccak256(0xFF | factory | salt | hash)
        + Op.BALANCE     # Cold access
        + Op.MSTORE(32, Op.ADD(Op.MLOAD(32), 1))  # salt++
    ),
    condition=...
)
```

The loop range is determined at bytecode generation time, not from calldata.

## Proposed Solution

### 1. Split Strategy Abstraction

```python
# In benchmark.py or a new module

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SplitStrategy(ABC):
    """
    Strategy for splitting transactions across a block.

    Subclasses define how calldata varies per transaction to ensure
    each transaction accesses different state (for cold-access benchmarks).
    """

    items_per_tx: int
    """Number of items (contracts, storage slots, etc.) accessed per transaction."""

    @abstractmethod
    def calldata_for_tx(self, tx_index: int) -> bytes:
        """
        Generate calldata for the transaction at the given index.

        Args:
            tx_index: Zero-based index of the transaction in the block

        Returns:
            Calldata bytes to use for this transaction
        """
        ...

    def total_items(self, num_txs: int) -> int:
        """Total items accessed across all transactions."""
        return self.items_per_tx * num_txs


@dataclass
class IdenticalSplitStrategy(SplitStrategy):
    """Default strategy: all transactions have identical (empty) calldata."""

    def calldata_for_tx(self, tx_index: int) -> bytes:
        return b""


@dataclass
class OffsetSplitStrategy(SplitStrategy):
    """
    Strategy using uint256 offset in calldata.

    Each transaction receives a 32-byte calldata containing the starting
    offset for that transaction's work. The attack bytecode reads this
    offset via CALLDATALOAD(0).

    Example with items_per_tx=1000:
        Tx 0: calldata = 0x0000...0000 (offset 0)
        Tx 1: calldata = 0x0000...03e8 (offset 1000)
        Tx 2: calldata = 0x0000...07d0 (offset 2000)
    """

    def calldata_for_tx(self, tx_index: int) -> bytes:
        offset = tx_index * self.items_per_tx
        return offset.to_bytes(32, 'big')
```

### 2. Extended `split_transaction`

```python
def split_transaction(
    self,
    tx: Transaction,
    gas_limit_cap: int | None,
    strategy: SplitStrategy | None = None,
) -> List[Transaction]:
    """
    Split a transaction that exceeds the gas limit cap into multiple transactions.

    Args:
        tx: The transaction to split
        gas_limit_cap: Maximum gas per transaction (from fork rules)
        strategy: Optional strategy for generating per-tx calldata.
                  If None, all transactions have identical calldata.
    """
    if gas_limit_cap is None or gas_limit_cap >= self.gas_benchmark_value:
        tx.gas_limit = HexNumber(self.gas_benchmark_value)
        if strategy:
            tx.data = strategy.calldata_for_tx(0)
        return [tx]

    num_splits = math.ceil(self.gas_benchmark_value / gas_limit_cap)
    remaining_gas = self.gas_benchmark_value

    split_transactions = []
    for i in range(num_splits):
        split_tx = tx.model_copy()
        split_tx.gas_limit = HexNumber(
            remaining_gas if i == num_splits - 1 else gas_limit_cap
        )
        remaining_gas -= gas_limit_cap
        split_tx.nonce = HexNumber(tx.nonce + i)

        # NEW: Apply strategy-specific calldata
        if strategy:
            split_tx.data = strategy.calldata_for_tx(i)

        split_transactions.append(split_tx)

    return split_transactions
```

### 3. Offset-Aware Bytecode Pattern

Standard pattern for attack contracts that support offset-based splitting:

```python
def generate_offset_aware_attack(
    *,
    items_per_tx: int,
    item_access_code: Bytecode,  # Code to access one item given salt on stack
    factory_address: Address,
) -> Bytecode:
    """
    Generate attack bytecode that reads starting offset from calldata.

    Calldata format: uint256 starting_offset (32 bytes)

    The bytecode:
    1. Reads starting offset from calldata
    2. Calculates end offset (start + items_per_tx)
    3. Loops from start to end, accessing items
    """
    return (
        # Read starting offset from calldata
        Op.CALLDATALOAD(0)  # Stack: [start_offset]

        # Calculate end offset
        + Op.DUP1
        + Op.PUSH2(items_per_tx)
        + Op.ADD  # Stack: [start_offset, end_offset]

        # Setup for CREATE2 address generation
        + Op.MSTORE(0, factory_address)
        + Op.MSTORE8(11, 0xFF)
        # ... (init_code_hash setup)

        # Main loop
        + While(
            condition=(
                Op.DUP2  # Copy current offset
                + Op.DUP2  # Copy end offset
                + Op.LT   # current < end?
            ),
            body=(
                # Store current offset as salt
                Op.DUP1
                + Op.MSTORE(32, ...)

                # Generate CREATE2 address
                + Op.SHA3(11, 85)

                # Access the item (BALANCE, EXTCODESIZE, etc.)
                + item_access_code

                # Increment offset
                + Op.SWAP1
                + Op.PUSH1(1)
                + Op.ADD
                + Op.SWAP1
            ),
        )
        + Op.POP
        + Op.POP
    )
```

### 4. Integration with BenchmarkCodeGenerator

```python
@dataclass(kw_only=True)
class BenchmarkCodeGenerator(ABC):
    """Abstract base class for generating benchmark bytecode."""

    attack_block: Bytecode
    setup: Bytecode = field(default_factory=Bytecode)
    cleanup: Bytecode = field(default_factory=Bytecode)
    tx_kwargs: Dict[str, Any] = field(default_factory=dict)
    # ... existing fields ...

    # NEW: Split strategy support
    _split_strategy: SplitStrategy | None = None

    @property
    def split_strategy(self) -> SplitStrategy | None:
        """
        Return the split strategy for this code generator.

        Override in subclasses that support offset-based splitting.
        Returns None for generators that don't support it (identical txs).
        """
        return self._split_strategy

    @abstractmethod
    def deploy_contracts(self, *, pre: Alloc, fork: Fork) -> Address:
        """Deploy any contracts needed for the benchmark."""
        ...
```

### 5. Bloatnet Implementation Example

```python
@dataclass
class BloatnetCodeGenerator(BenchmarkCodeGenerator):
    """Code generator for bloatnet cold-access benchmarks."""

    factory_address: Address
    items_per_tx: int
    access_opcodes: Bytecode  # e.g., Op.BALANCE + Op.EXTCODESIZE

    def __post_init__(self):
        # Configure split strategy
        self._split_strategy = OffsetSplitStrategy(items_per_tx=self.items_per_tx)

        # Generate offset-aware attack bytecode
        self.attack_block = self._generate_attack_bytecode()

    def _generate_attack_bytecode(self) -> Bytecode:
        return generate_offset_aware_attack(
            items_per_tx=self.items_per_tx,
            item_access_code=self.access_opcodes,
            factory_address=self.factory_address,
        )

    def deploy_contracts(self, *, pre: Alloc, fork: Fork) -> Address:
        code = self.attack_block
        self._contract_address = pre.deploy_contract(code=code)
        return self._contract_address
```

### 6. Usage in Tests

```python
@pytest.mark.valid_from("Prague")
def test_bloatnet_balance_extcodesize(
    benchmark_test: BenchmarkTestFiller,
    pre: Alloc,
    fork: Fork,
    gas_benchmark_value: int,
) -> None:
    """BloatNet cold-access benchmark with proper multi-tx support."""

    # Calculate items per tx based on gas costs
    gas_costs = fork.gas_costs()
    tx_gas_limit = fork.transaction_gas_limit_cap() or gas_benchmark_value
    items_per_tx = calculate_items_per_tx(tx_gas_limit, gas_costs)

    # Deploy factory (stub or real)
    factory_address = pre.deploy_contract(code=Bytecode(), stub="bloatnet_factory")

    # Create code generator with offset support
    code_gen = BloatnetCodeGenerator(
        factory_address=factory_address,
        items_per_tx=items_per_tx,
        access_opcodes=Op.POP(Op.BALANCE) + Op.POP(Op.EXTCODESIZE),
    )

    # BenchmarkTest automatically uses split_strategy from code_gen
    yield BenchmarkTest(
        pre=pre,
        code_generator=code_gen,
        gas_benchmark_value=gas_benchmark_value,
    )
```

## Migration Path

### Phase 1: Infrastructure (non-breaking)
1. Add `SplitStrategy` base class and implementations
2. Add optional `strategy` parameter to `split_transaction`
3. Add `split_strategy` property to `BenchmarkCodeGenerator`
4. All existing tests continue to work (strategy=None)

### Phase 2: Bytecode Patterns
1. Document offset-aware bytecode pattern
2. Create helper functions for generating offset-aware loops
3. Add examples to documentation

### Phase 3: Test Migration
1. Update bloatnet tests to use offset-aware bytecode
2. Update gas calculations (all cold, no warm transition)
3. Validate results match expected cold-access costs

### Phase 4: Cleanup
1. Remove manual transaction splitting from individual tests
2. Deprecate tests that don't properly handle cold access

## Benefits

1. **Correct benchmarks**: Actually measures cold access across all transactions
2. **Centralized logic**: Split strategy lives in `benchmark.py`, not scattered across tests
3. **Backward compatible**: Existing tests work unchanged
4. **Extensible**: Other split strategies possible (e.g., different calldata encodings)
5. **Self-documenting**: Strategy classes make intent explicit
6. **Testable**: Strategies can be unit tested independently

## Gas Model Implications

With proper cold-access-across-txs, the gas model simplifies:

**Current (mixed cold/warm):**
```python
@dataclass
class LoopGasModel:
    overhead_per_contract: int
    cost_per_iteration: int
    cold_warm_diff: int  # First call penalty

    def calls_per_contract(self, available_gas: int, num_contracts: int) -> int:
        # Complex: accounts for cold first call, warm subsequent
        ...
```

**With offset strategy (all cold):**
```python
@dataclass
class ColdAccessGasModel:
    overhead_per_item: int
    cold_access_cost: int  # Always cold!

    def items_per_tx(self, available_gas: int) -> int:
        # Simple: all accesses are cold
        return available_gas // (self.overhead_per_item + self.cold_access_cost)
```

## Open Questions

1. **Calldata encoding**: Should we standardize on uint256 offset, or support other encodings?

2. **Factory coordination**: How does the attack contract know how many contracts exist? Currently reads from factory storage - should offset be validated against this?

3. **Gas calculation**: With all-cold access, do we still need `LoopGasModel` complexity, or can we simplify?

4. **Testing**: How do we validate that a benchmark is correctly measuring cold access? Add assertions on expected gas usage?

## Related Documents

- `tmp/bloatnet_num_txs_refactor.md` - Short-term fixture refactoring
- `tmp/bloatnet_single_opcode_inconsistency.md` - Gas calculation inconsistency analysis
