import ctypes
import logging
import struct

logger = logging.getLogger(__name__)

CACHE_LINE_BYTES = 64


class CacheLineAlignedBuffer:
    """
    64-byte cache-line aligned memory buffer.
    Prevents false sharing on multi-core systems where two threads
    modify adjacent variables that land on the same cache line.
    Critical for the Quorum loop where 11 agents write results concurrently.
    """

    def __init__(self, size_bytes: int):
        self.size = size_bytes
        padded = size_bytes + CACHE_LINE_BYTES
        raw = (ctypes.c_uint8 * padded)()
        addr = ctypes.addressof(raw)
        offset = (-addr) % CACHE_LINE_BYTES
        self._buf = (ctypes.c_uint8 * size_bytes).from_address(addr + offset)
        self._raw = raw
        logger.debug(f"[CACHE ALIGN] Allocated {size_bytes}B buffer aligned to {CACHE_LINE_BYTES}B")

    def write(self, data: bytes, offset: int = 0) -> None:
        n = min(len(data), self.size - offset)
        ctypes.memmove(ctypes.addressof(self._buf) + offset, data, n)

    def read(self, n: int, offset: int = 0) -> bytes:
        return bytes(self._buf[offset : offset + n])
