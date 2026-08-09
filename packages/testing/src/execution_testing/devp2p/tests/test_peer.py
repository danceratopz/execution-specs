"""
Tests for how the peer bounds the responses it serves.

A response is bounded by serialized bytes, not only by a count of items.
Clients cap the size of every message they read - geth's `maxMessageSize`
is ten mebibytes, and exceeding it drops the peer rather than truncating
the message - so two multi-megabyte bodies have to travel as two
responses. EIP-7934 caps a block at eight mebibytes, which puts two of
them in one response over that cap, and blocks that large are exactly
what the `eip7934_block_rlp_limit` fixtures serve.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, cast

from ..peer import (
    BLOCK_BODIES,
    MAX_BODIES_PER_RESPONSE,
    SOFT_RESPONSE_LIMIT,
    MockPeer,
)
from ..rlpx import RLPxSession

LARGE_BODY_SIZE = 8 * 1024 * 1024
"""A body the size EIP-7934 allows a block to reach."""


def _hash(index: int) -> bytes:
    """Return a distinct block hash for `index`."""
    return index.to_bytes(32, "big")


@dataclass
class _StubHead:
    """The head fields the peer reads when a hash is unknown."""

    number: int = 1
    block_hash: bytes = b"\xaa" * 32


@dataclass
class _StubChain:
    """A chain that only has to answer for its head."""

    head: _StubHead = field(default_factory=_StubHead)


class _StubChains:
    """The bodies a peer holds, keyed by block hash."""

    def __init__(self, bodies: Dict[bytes, bytes]) -> None:
        """Hold `bodies` and present a chain to report as current."""
        self._bodies = bodies
        self.current = _StubChain()

    def body_rlp_by_hash(self, block_hash: bytes) -> bytes | None:
        """Return the body held under `block_hash`, if any."""
        return self._bodies.get(block_hash)


class _RecordingSession:
    """A session that keeps what was written instead of sending it."""

    def __init__(self) -> None:
        """Start with nothing written."""
        self.messages: List[Tuple[int, bytes]] = []

    def write_message(self, code: int, payload: bytes) -> None:
        """Record one message."""
        self.messages.append((code, payload))


def _serve(bodies: Dict[bytes, bytes], hashes: List[bytes]) -> int:
    """
    Ask a peer holding `bodies` for `hashes`, and return how many it sent.

    The response is counted rather than decoded: these payloads reach
    megabytes, and a pure Python RLP decode of one takes long enough to
    dominate the suite.
    """
    peer = MockPeer(
        host="127.0.0.1",
        port=30303,
        remote_public_key=b"\x00" * 64,
        private_key=b"\x01" * 32,
        network_id=1,
    )
    peer._chains = cast(Any, _StubChains(bodies))
    session = _RecordingSession()
    peer._serve_bodies(cast(RLPxSession, session), 1, hashes)

    assert len(session.messages) == 1
    code, payload = session.messages[0]
    assert code == BLOCK_BODIES
    served = peer.statistics.bodies_served
    # The response carries every served body and nothing else of size.
    expected = sum(len(bodies[block_hash]) for block_hash in hashes[:served])
    assert expected <= len(payload) <= expected + 16
    return served


class TestBodyResponseSize:
    """One response never carries more bytes than a client will read."""

    def test_two_large_bodies_are_split(self) -> None:
        """Two eight mebibyte bodies do not share one response."""
        bodies = {
            _hash(1): b"\x00" * LARGE_BODY_SIZE,
            _hash(2): b"\x00" * LARGE_BODY_SIZE,
        }
        assert _serve(bodies, [_hash(1), _hash(2)]) == 1

    def test_one_oversized_body_is_still_served(self) -> None:
        """A body larger than the limit is served rather than withheld."""
        body = b"\x00" * LARGE_BODY_SIZE
        assert len(body) > SOFT_RESPONSE_LIMIT
        assert _serve({_hash(1): body}, [_hash(1)]) == 1

    def test_small_bodies_share_one_response(self) -> None:
        """Bodies that fit are still batched, as they always were."""
        bodies = {_hash(index): bytes([index]) for index in range(1, 33)}
        assert _serve(bodies, sorted(bodies)) == 32

    def test_unknown_hash_ends_the_response(self) -> None:
        """An unheld hash still stops the response where it is."""
        assert _serve({_hash(1): b"\x01"}, [_hash(1), _hash(2)]) == 1

    def test_item_cap_still_applies(self) -> None:
        """The count cap bounds a request for many tiny bodies."""
        wanted = MAX_BODIES_PER_RESPONSE + 10
        bodies = {_hash(index): b"\x01" for index in range(wanted)}
        hashes = [_hash(index) for index in range(wanted)]
        assert _serve(bodies, hashes) == MAX_BODIES_PER_RESPONSE

