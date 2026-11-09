"""Private native-program cache and JIT launch operations for the CLI compiler.

The native lock is nonblocking and owns an allocated descriptor until process exit
or exec; it never replaces a descriptor inherited from the caller. The compiler
supplies the bounded wait; the CPython-hosted compiler bypasses this cache.
Programs do not call the private runtime primitives directly.
"""
import sys

__all__ = ["NATIVE", "try_lock", "lock_fd", "file_hash", "ignored_signals"]
NATIVE: bool = sys.implementation.name == "pystachy"


def try_lock(path: str) -> int:
    """Return 1 for an acquired lock, 0 for busy, and -1 for an unusable path."""
    return __pys_cache_lock(path)


def lock_fd() -> int:
    """Return our current lock descriptor, or -1 before acquiring any lock."""
    return __pys_cache_lock_fd()


def file_hash(path: str, limit: int) -> str:
    """Hash raw bytes with the cache's FNV digest, or return empty on failure."""
    return __pys_cache_file_hash(path, limit)


def ignored_signals() -> int:
    """Return the standard signals this process ignores, bit s-1 for signal s."""
    return __pys_ignored_signals()
