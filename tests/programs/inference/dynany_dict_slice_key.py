# pystachy: dynamic-any
# A dict's slice through Any values hashes the slice before it looks it up, as CPython 3.12's
# slices hash: its start, stop and step in turn, so an unhashable one raises TypeError and an
# object's __hash__ runs, and a hashable slice then raises the KeyError that no dict key matches.
from typing import Any


class H:
    def __hash__(self) -> int:
        print("hash ran")
        return 1


d: Any = {"a": 1}
bad: Any = [1]
lo: Any = 1
h: Any = H()
try:
    print(d[bad:])
except (KeyError, TypeError) as e:
    print(type(e).__name__, e)
try:
    print(d[lo:2])
except (KeyError, TypeError) as e:
    print(type(e).__name__, e)
try:
    print(d[h:])
except (KeyError, TypeError) as e:
    print(type(e).__name__)
try:
    print(d[1:bad:h])
except (KeyError, TypeError) as e:
    print(type(e).__name__, e)
try:
    print(d[1:2:bad])
except (KeyError, TypeError) as e:
    print(type(e).__name__, e)
