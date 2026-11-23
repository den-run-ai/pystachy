import sys

__all__ = ["default"]
default = 5
_private = 7
option = 11
hidden = 13

if sys.argv:
    __all__.append("_private")
    __all__.extend(["option"])
if len(sys.argv) > 10:
    __all__.append("hidden")
