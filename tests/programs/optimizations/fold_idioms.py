# Idioms the loader decides as CPython does at import time: TYPE_CHECKING imported with the
# fallback for an old typing module (the except clause never runs, so the name is still
# TYPE_CHECKING), sys.platform tested against a tuple or list of Windows names, and an imported
# module's __name__ == "__main__" inside and/or. Their if statements' imports are never loaded
# (tests/loader/never.py has a syntax error).
import sys
import loader.mainguard

try:
    from typing import TYPE_CHECKING
except ImportError:
    TYPE_CHECKING = False
if TYPE_CHECKING:
    import loader.never
if sys.platform in ("win32", "cygwin"):
    import loader.never
elif sys.platform not in ["win32", "msys"]:
    print("posix")


def count(n: int) -> int:
    return n + 1


print(count(1), TYPE_CHECKING, loader.mainguard.v)
