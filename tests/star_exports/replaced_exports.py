import sys

a = 1
b = 2
_private = 8
__all__ = ["a"]
if len(sys.argv) > 0:
    __all__ = ["b", "_private"]
