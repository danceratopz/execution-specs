"""
Incremental Keccak-256 used by the RLPx frame MACs.

The RLPx transport keeps a running Keccak-256 state per direction, and
reads a digest from it after every frame *without* finalizing it. Neither
``hashlib`` (which implements SHA3, a different padding rule) nor the
one-shot Keccak in ``pycryptodome`` (which forbids updates after a digest)
can express that, so the sponge is implemented here.
"""

from typing import List

RATE_BYTES = 136
"""Keccak-256 bitrate in bytes (1600 bits state - 512 bits capacity)."""

_ROUND_CONSTANTS = [
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808A,
    0x8000000080008000,
    0x000000000000808B,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008A,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000A,
    0x000000008000808B,
    0x800000000000008B,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800A,
    0x800000008000000A,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008,
]

_ROTATION_OFFSETS = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]

_MASK = (1 << 64) - 1


def _rotate_left(value: int, shift: int) -> int:
    """Rotate a 64 bit lane left by `shift` bits."""
    return ((value << shift) | (value >> (64 - shift))) & _MASK


def _permute(lanes: List[List[int]]) -> None:
    """Apply the 24 round keccak-f[1600] permutation to `lanes`."""
    for round_constant in _ROUND_CONSTANTS:
        # Theta.
        column_parities = [
            lanes[x][0] ^ lanes[x][1] ^ lanes[x][2] ^ lanes[x][3] ^ lanes[x][4]
            for x in range(5)
        ]
        for x in range(5):
            correction = column_parities[(x + 4) % 5] ^ _rotate_left(
                column_parities[(x + 1) % 5], 1
            )
            for y in range(5):
                lanes[x][y] ^= correction

        # Rho and pi.
        rotated = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                rotated[y][(2 * x + 3 * y) % 5] = _rotate_left(
                    lanes[x][y], _ROTATION_OFFSETS[x][y]
                )

        # Chi.
        for x in range(5):
            for y in range(5):
                lanes[x][y] = rotated[x][y] ^ (
                    ~rotated[(x + 1) % 5][y] & rotated[(x + 2) % 5][y]
                )

        # Iota.
        lanes[0][0] ^= round_constant


def _absorb_block(lanes: List[List[int]], block: bytes) -> None:
    """Exclusive-or one rate sized `block` into `lanes` and permute."""
    for offset in range(0, RATE_BYTES, 8):
        lane = int.from_bytes(block[offset : offset + 8], "little")
        index = offset // 8
        lanes[index % 5][index // 5] ^= lane
    _permute(lanes)


class Keccak256:
    """
    A Keccak-256 sponge that can be digested and then updated again.

    `digest` leaves the absorbing state untouched: it pads and squeezes a
    copy. This is what allows a single instance to act as the running
    egress or ingress MAC of an RLPx connection.
    """

    _lanes: List[List[int]]
    _buffer: bytes

    def __init__(self, data: bytes = b"") -> None:
        """Initialize the sponge, optionally absorbing `data`."""
        self._lanes = [[0] * 5 for _ in range(5)]
        self._buffer = b""
        self.update(data)

    def update(self, data: bytes) -> None:
        """Absorb `data` into the sponge."""
        self._buffer += data
        while len(self._buffer) >= RATE_BYTES:
            _absorb_block(self._lanes, self._buffer[:RATE_BYTES])
            self._buffer = self._buffer[RATE_BYTES:]

    def digest(self) -> bytes:
        """
        Return the 32 byte digest of everything absorbed so far.

        The sponge remains usable: further `update` calls continue from
        the pre-padding state.
        """
        lanes = [column.copy() for column in self._lanes]
        block = bytearray(RATE_BYTES)
        block[: len(self._buffer)] = self._buffer
        block[len(self._buffer)] ^= 0x01
        block[RATE_BYTES - 1] ^= 0x80
        _absorb_block(lanes, bytes(block))

        output = bytearray()
        for index in range(4):
            output += lanes[index % 5][index // 5].to_bytes(8, "little")
        return bytes(output)


def keccak256(data: bytes) -> bytes:
    """Return the Keccak-256 digest of `data`."""
    return Keccak256(data).digest()
