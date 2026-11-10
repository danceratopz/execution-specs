"""
The blocks a mock peer serves, from either of two fixture sources.

An Engine X fixture stores each block as the `engine_newPayload` request
that delivers it. A payload omits the header fields the client is
expected to derive - the two transaction and withdrawal tries, and the
constants a post-merge header carries - so serving those blocks over the
wire means putting them back. The reconstruction is self checking: a
rebuilt header is only accepted if its hash equals the block hash the
payload already claims.

A Blockchain Test X fixture stores each block as its RLP, which a block
before the merge is only ever expressed as (a payload has no difficulty,
nonce or uncles). Those blocks are served as their RLP encodes them,
uncles included.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Protocol, Sequence

import ethereum_rlp as eth_rlp
from ethereum_rlp.exceptions import DecodingError
from ethereum_types.numeric import Uint
from trie import HexaryTrie

from execution_testing.base_types import Bytes, Hash
from execution_testing.fixtures.blockchain import (
    FixtureEngineNewPayload,
    FixtureExecutionPayload,
    FixtureHeader,
)
from execution_testing.forks import Requests
from execution_testing.test_types.block_types import Withdrawal

from .protocol import encode_list, encode_transactions

logger = logging.getLogger(__name__)

EMPTY_OMMERS_RLP = b"\xc0"


class ChainReconstructionError(Exception):
    """Raised when a payload cannot be turned back into a valid block."""


def _transactions_root(transactions: Sequence[Bytes]) -> bytes:
    """Return the transactions trie root over raw transaction bytes."""
    trie = HexaryTrie(db={})
    for index, transaction in enumerate(transactions):
        trie.set(eth_rlp.encode(Uint(index)), transaction)
    return trie.root_hash


class ServedBlock(Protocol):
    """What a mock peer and its consumer read of a block it serves."""

    @property
    def bal_rlp(self) -> bytes | None:
        """Return the block's RLP encoded BAL, `None` before Amsterdam."""
        ...

    @property
    def number(self) -> int:
        """Return the block number."""
        ...

    @property
    def block_hash(self) -> Hash:
        """Return the block hash."""
        ...

    @property
    def parent_hash(self) -> Hash:
        """Return the parent's block hash."""
        ...

    @property
    def timestamp(self) -> int:
        """Return the block timestamp."""
        ...

    @property
    def difficulty(self) -> int:
        """Return the block difficulty (zero after the merge)."""
        ...

    @property
    def state_root(self) -> Hash:
        """Return the state root the header commits to."""
        ...

    @property
    def owes_body(self) -> bool:
        """
        Return whether a client must fetch the body to hold the block.

        A body with no item in any of its lists is derived from its
        header, so syncing clients skip it.
        """
        ...

    def header_rlp(self) -> bytes:
        """Return the RLP encoded header."""
        ...

    def body_rlp(self) -> bytes:
        """Return the RLP encoded block body."""
        ...


@dataclass
class Block:
    """One block rebuilt from its Engine API payload, ready to be served."""

    header: FixtureHeader
    transactions: List[Bytes]
    withdrawals: List[Withdrawal] | None
    bal_rlp: bytes | None = None
    """
    The block's RLP encoded EIP-7928 BAL, as its payload carries it;
    `None` before Amsterdam. It is not part of the body: eth/71
    (EIP-8159) serves it through its own request pair.
    """

    @property
    def number(self) -> int:
        """Return the block number."""
        return int(self.header.number)

    @property
    def block_hash(self) -> Hash:
        """Return the block hash."""
        return self.header.block_hash

    @property
    def parent_hash(self) -> Hash:
        """Return the parent's block hash."""
        return self.header.parent_hash

    @property
    def timestamp(self) -> int:
        """Return the block timestamp."""
        return int(self.header.timestamp)

    @property
    def difficulty(self) -> int:
        """Return the block difficulty (zero after the merge)."""
        return int(self.header.difficulty)

    @property
    def state_root(self) -> Hash:
        """Return the state root the header commits to."""
        return self.header.state_root

    @property
    def owes_body(self) -> bool:
        """Return whether the body holds a transaction or withdrawal."""
        return bool(self.transactions or self.withdrawals)

    def header_rlp(self) -> bytes:
        """Return the RLP encoded header."""
        return bytes(self.header.rlp)

    def body_rlp(self) -> bytes:
        """Return the RLP encoded block body."""
        items = [
            encode_transactions([bytes(t) for t in self.transactions]),
            EMPTY_OMMERS_RLP,
        ]
        if self.withdrawals is not None:
            items.append(
                encode_list(
                    [
                        eth_rlp.encode(withdrawal.to_serializable_list())
                        for withdrawal in self.withdrawals
                    ]
                )
            )
        return encode_list(items)


HEADER_PARENT_HASH = 0
HEADER_STATE_ROOT = 3
HEADER_DIFFICULTY = 7
HEADER_NUMBER = 8
HEADER_TIMESTAMP = 11
HEADER_MINIMUM_FIELDS = 15
"""Every header since Frontier has these 15 fields; later forks append."""


class UndecodableBlockError(ChainReconstructionError):
    """
    Raised when a fixture's block RLP is not a block a peer can serve.

    The RLP does not decode, or does not decode to a header and body
    lists: a client would drop the peer for the response rather than
    judge the block, so such a block has no devp2p representation.
    """


def _uint(field: object, name: str) -> int:
    """Return the integer a header `field` encodes, or raise."""
    if not isinstance(field, bytes) or field[:1] == b"\x00":
        raise UndecodableBlockError(f"header {name} is not an integer")
    return int.from_bytes(field, "big")


def _hash32(field: object, name: str) -> Hash:
    """Return the hash a header `field` holds, or raise."""
    if not isinstance(field, bytes) or len(field) != 32:
        raise UndecodableBlockError(f"header {name} is not a 32-byte hash")
    return Hash(field)


@dataclass(frozen=True)
class RlpBlock:
    """
    One block served as its fixture RLP encodes it, uncles included.

    The header and the body are served as the re-encoded parts of the
    decoded block, which is the fixture's bytes for any canonical
    encoding; a caller holding the block's declared hash checks it
    against `block_hash`.
    """

    _header_rlp: bytes
    _body_rlp: bytes
    number: int
    block_hash: Hash
    parent_hash: Hash
    timestamp: int
    difficulty: int
    state_root: Hash
    owes_body: bool
    bal_rlp: bytes | None = None

    @classmethod
    def from_rlp(cls, block_rlp: bytes) -> "RlpBlock":
        """
        Split a block's RLP into its served header and body.

        Raise `UndecodableBlockError` when the RLP does not decode to a
        header list of at least the Frontier fields followed by the body
        lists.
        """
        try:
            decoded = eth_rlp.decode(block_rlp)
        except DecodingError as error:
            raise UndecodableBlockError(
                f"block RLP does not decode: {error}"
            ) from error
        if (
            not isinstance(decoded, list)
            or len(decoded) < 3
            or not all(isinstance(item, list) for item in decoded)
        ):
            raise UndecodableBlockError(
                "block RLP is not a header list followed by body lists"
            )
        header, *body = decoded
        if len(header) < HEADER_MINIMUM_FIELDS:
            raise UndecodableBlockError(
                f"header has {len(header)} fields, fewer than "
                f"{HEADER_MINIMUM_FIELDS}"
            )
        header_rlp = eth_rlp.encode(header)
        return cls(
            _header_rlp=header_rlp,
            _body_rlp=eth_rlp.encode(body),
            number=_uint(header[HEADER_NUMBER], "number"),
            block_hash=Hash(Bytes(header_rlp).keccak256()),
            parent_hash=_hash32(header[HEADER_PARENT_HASH], "parent hash"),
            timestamp=_uint(header[HEADER_TIMESTAMP], "timestamp"),
            difficulty=_uint(header[HEADER_DIFFICULTY], "difficulty"),
            state_root=_hash32(header[HEADER_STATE_ROOT], "state root"),
            owes_body=any(len(items) > 0 for items in body),
        )

    def header_rlp(self) -> bytes:
        """Return the RLP encoded header."""
        return self._header_rlp

    def body_rlp(self) -> bytes:
        """Return the RLP encoded block body."""
        return self._body_rlp


def block_from_payload(payload: FixtureEngineNewPayload) -> Block:
    """
    Rebuild the block that `payload` delivers.

    Raise `ChainReconstructionError` if the rebuilt header does not hash
    to the block hash the payload declares, which is what would happen if
    a fork introduced a header field this reconstruction does not know
    about.
    """
    execution_payload = payload.params[0]
    if not isinstance(execution_payload, FixtureExecutionPayload):
        raise ChainReconstructionError("payload has no execution payload")

    withdrawals = execution_payload.withdrawals
    beacon_root = payload.params[2] if len(payload.params) > 2 else None
    execution_requests = payload.params[3] if len(payload.params) > 3 else None
    block_access_list = execution_payload.block_access_list

    header = FixtureHeader(
        parent_hash=execution_payload.parent_hash,
        fee_recipient=execution_payload.fee_recipient,
        state_root=execution_payload.state_root,
        transactions_trie=Hash(
            _transactions_root(execution_payload.transactions)
        ),
        receipts_root=execution_payload.receipts_root,
        logs_bloom=execution_payload.logs_bloom,
        number=execution_payload.number,
        gas_limit=execution_payload.gas_limit,
        gas_used=execution_payload.gas_used,
        timestamp=execution_payload.timestamp,
        extra_data=execution_payload.extra_data,
        prev_randao=execution_payload.prev_randao,
        base_fee_per_gas=execution_payload.base_fee_per_gas,
        withdrawals_root=(
            None
            if withdrawals is None
            else Hash(Withdrawal.list_root(withdrawals))
        ),
        blob_gas_used=execution_payload.blob_gas_used,
        excess_blob_gas=execution_payload.excess_blob_gas,
        parent_beacon_block_root=beacon_root,
        requests_hash=(
            None
            if execution_requests is None
            else Hash(bytes(Requests(requests_lists=list(execution_requests))))
        ),
        block_access_list_hash=(
            None
            if block_access_list is None
            else block_access_list.keccak256()
        ),
        slot_number=execution_payload.slot_number,
    )

    if header.block_hash != execution_payload.block_hash:
        raise ChainReconstructionError(
            f"reconstructed block {execution_payload.number} hashes to "
            f"{header.block_hash} but the payload declares "
            f"{execution_payload.block_hash}"
        )

    return Block(
        header=header,
        transactions=list(execution_payload.transactions),
        withdrawals=None if withdrawals is None else list(withdrawals),
        bal_rlp=(
            None if block_access_list is None else bytes(block_access_list)
        ),
    )


class Chain:
    """
    The canonical chain a mock peer serves for one test.

    Blocks are indexed by both number and hash because a syncing client
    walks headers backwards by hash from the head it was told to reach,
    then asks for bodies by hash.
    """

    def __init__(self, genesis: FixtureHeader, blocks: Sequence[ServedBlock]):
        """Build a chain of `blocks` descending from `genesis`."""
        self.genesis = genesis
        self.blocks = list(blocks)
        self._by_number: Dict[int, ServedBlock] = {
            block.number: block for block in self.blocks
        }
        self._by_hash: Dict[Hash, ServedBlock] = {
            block.block_hash: block for block in self.blocks
        }

    @property
    def head(self) -> ServedBlock:
        """Return the last block of the chain."""
        return self.blocks[-1]

    @property
    def total_difficulty(self) -> int:
        """
        Return the total difficulty of the head: the sum of the
        difficulties of genesis and every block.

        Only eth/68's Status carries it. After the merge every block's
        difficulty is zero, so it is the total difficulty of genesis.
        """
        return int(self.genesis.difficulty) + sum(
            block.difficulty for block in self.blocks
        )

    def header_rlp_by_number(self, number: int) -> bytes | None:
        """Return the RLP of the header at `number`, if held."""
        if number == int(self.genesis.number):
            return bytes(self.genesis.rlp)
        block = self._by_number.get(number)
        return None if block is None else block.header_rlp()

    def number_of(self, block_hash: Hash) -> int | None:
        """Return the number of the block with `block_hash`, if held."""
        if block_hash == self.genesis.block_hash:
            return int(self.genesis.number)
        block = self._by_hash.get(block_hash)
        return None if block is None else block.number

    def body_rlp_by_hash(self, block_hash: Hash) -> bytes | None:
        """
        Return the RLP of the body with `block_hash`, if held.

        The genesis body is empty by definition, but its shape follows
        its header: a genesis whose header commits to a withdrawals
        root must serve the empty withdrawals list too, or the body
        cannot validate against the header.
        """
        if block_hash == self.genesis.block_hash:
            items = [encode_list([]), EMPTY_OMMERS_RLP]
            if self.genesis.withdrawals_root is not None:
                items.append(encode_list([]))
            return encode_list(items)
        block = self._by_hash.get(block_hash)
        return None if block is None else block.body_rlp()

    def bal_rlp_by_hash(self, block_hash: Hash) -> bytes | None:
        """Return the BAL RLP of the block with `block_hash`."""
        block = self._by_hash.get(block_hash)
        return None if block is None else block.bal_rlp


class ServedChains:
    """
    Every chain a peer has served over one connection.

    A client is reused across the tests of a pre-allocation group, and
    each test installs its own chain. The client's downloader does not
    forget the previous one that fast: it keeps asking for blocks of the
    chain it was syncing when the test ended. A real peer would still
    hold those blocks, so this one does too, and answers from whichever
    installed chain a requested hash belongs to.

    Requests that name a block by number are answered from the current
    chain only, since a number alone does not identify a chain.
    """

    def __init__(self) -> None:
        """Start with no chain installed."""
        self._chain_by_hash: Dict[Hash, Chain] = {}
        self._current: Chain | None = None

    def install(self, chain: Chain) -> None:
        """Serve `chain` from now on, keeping earlier chains available."""
        self._current = chain
        for block in chain.blocks:
            self._chain_by_hash.setdefault(block.block_hash, chain)

    @property
    def current(self) -> Chain:
        """Return the chain currently being served."""
        assert self._current is not None, "no chain installed"
        return self._current

    def chain_for_hash(self, block_hash: Hash) -> Chain | None:
        """
        Return the chain holding `block_hash`, if any.

        The current chain is preferred whenever it holds the block. A
        block shared by several chains has the same ancestors on each,
        but only the current chain leads from it to the head the client
        was told to reach, so a forward walk must follow that one.

        The current chain is read once: the serving thread looks up
        bodies and BALs without the peer's lock, and a chain installed
        between two reads would be returned for a block it lacks.
        """
        current = self._current
        if current is not None and current.number_of(block_hash) is not None:
            return current
        return self._chain_by_hash.get(block_hash)

    def body_rlp_by_hash(self, block_hash: Hash) -> bytes | None:
        """Return the RLP of the body with `block_hash`, if held."""
        chain = self.chain_for_hash(block_hash)
        return None if chain is None else chain.body_rlp_by_hash(block_hash)

    def bal_rlp_by_hash(self, block_hash: Hash) -> bytes | None:
        """Return the BAL RLP of the block with `block_hash`."""
        chain = self.chain_for_hash(block_hash)
        return None if chain is None else chain.bal_rlp_by_hash(block_hash)


def chain_from_payloads(
    genesis: FixtureHeader, payloads: Sequence[FixtureEngineNewPayload]
) -> Chain:
    """
    Build the chain that `payloads` describe, rooted at `genesis`.

    Every payload must reconstruct, and every block must name its
    predecessor: a chain served with a gap in it would make a client's
    sync failure look like a client bug.
    """
    return linked_chain(
        genesis, [block_from_payload(payload) for payload in payloads]
    )


def linked_chain(
    genesis: FixtureHeader, blocks: Sequence[ServedBlock]
) -> Chain:
    """
    Return the chain of `blocks` above `genesis`, each naming the last.

    Raise `ChainReconstructionError` at the first block that does not
    name its predecessor: a chain served with a gap in it would make a
    client's sync failure look like a client bug.
    """
    parent_hash = genesis.block_hash
    for block in blocks:
        if block.parent_hash != parent_hash:
            raise ChainReconstructionError(
                f"block {block.number} does not extend its predecessor"
            )
        parent_hash = block.block_hash

    return Chain(genesis, blocks)
