import sys

setting = 1
fallback = 2
__all__ = ["setting", "fallback"]
if sys.argv:
    __all__ = ["setting"]
