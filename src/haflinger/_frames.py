"""The frames that pass between Haflinger and its worker process (ADR-010): a frame is its
length as eight bytes, big-endian, then that many bytes of UTF-8 text."""

import struct
from typing import BinaryIO

LENGTH = struct.Struct(">Q")


def frames(*bodies: bytes) -> bytes:
    return b"".join(LENGTH.pack(len(body)) + body for body in bodies)


def read_frame(stream: BinaryIO) -> bytes | None:
    """The next frame, blocking; None where the stream ends before one starts."""
    header = _read_exactly(stream, LENGTH.size)
    if header is None:
        return None
    (length,) = LENGTH.unpack(header)
    body = _read_exactly(stream, length)
    if body is None:
        raise EOFError("the stream ended within a frame")
    return body


def _read_exactly(stream: BinaryIO, size: int) -> bytes | None:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            if remaining == size:
                return None
            raise EOFError("the stream ended within a frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
