# Documented deviation (#1513): a star import sees the __all__ that the module's top level binds,
# but not its extension in an if statement's branch, so it takes only a. CPython runs the branch,
# takes __all__ = ["a", "b"] and prints "3 4".
b = "main's b"
from devmods.allext import *

print(a, b)
