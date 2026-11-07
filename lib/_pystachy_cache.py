"""Private native-program cache operations for the CLI compiler.

The native lock is nonblocking and stays on descriptor 9 until process exit or
exec. The compiler supplies the bounded wait and its CPython-hosted fallback.
Programs do not call the private runtime primitive directly.
"""
import sys

__all__ = ["NATIVE", "try_lock", "file_hash"]
NATIVE: bool = sys.implementation.name == "pystachy"


def try_lock(path: str) -> int:
    """Return 1 for an acquired lock, 0 for busy, and -1 for an unusable path."""
    return __pys_cache_lock(path)


def file_hash(path: str, limit: int) -> str:
    """Hash raw bytes with the cache's FNV digest, or return empty on failure."""
    return __pys_cache_file_hash(path, limit)
