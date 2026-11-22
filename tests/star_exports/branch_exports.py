import sys

public = 3
other = 7
_private = 13
if len(sys.argv) > 10:
    __all__ = ["_private", "public"]
