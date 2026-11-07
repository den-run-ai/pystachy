"""Native copying helper for ctypes' ordinary Python support classes."""
import ffi

__all__ = ["bytes_at"]


def bytes_at(address: int, size: int) -> bytes:
    return ffi.bytes_at(address, size)
