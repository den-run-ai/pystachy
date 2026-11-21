# error: enum.EnumDict is not supported: it is the namespace of a class body that CPython's EnumType.__prepare__ makes
# CPython's EnumDict is a dict that tracks an enum class body's member names (printing {'a': 1})
from enum import EnumDict

d = EnumDict()
d["a"] = 1
print(d)
