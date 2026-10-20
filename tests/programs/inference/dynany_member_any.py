# pystachy: dynamic-any
# in, index() and count() compare an Any item of a tuple, or of an iterator object, with a typed
# value as == compares them, after identity, as CPython's PyObject_RichCompareBool does: an Any
# value may equal a value of any type, where Pystachy took them for never equal.
from typing import Any


class Count:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __iter__(self) -> "Count":
        return self

    def __next__(self) -> Any:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i


x: Any = 2
nan: Any = float("nan")
t = (1, x, "s")
print(2 in Count(3), 4 in Count(3), 2.0 in Count(2), "s" in Count(2))
print(2 in (x,), 2 in t, t.index(2), t.count(2.0), "s" in t, 3 in t)
print(nan in (nan,), (nan,).count(nan), nan in [nan])
