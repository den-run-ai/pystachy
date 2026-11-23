import sys

a = 2
b = 5
__all__ = ["a"]
if len(sys.argv) > 10:
    __all__ += ["b"]
