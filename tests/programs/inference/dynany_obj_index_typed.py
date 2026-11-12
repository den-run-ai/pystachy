# pystachy: dynamic-any
# A typed object's __index__() in a module that opts in to dynamic Any, beside an Any value's
# in a slice.
from typing import Any


class I:
    def __init__(self, n: int) -> None:
        self.n = n

    def __index__(self) -> int:
        return self.n


xs = [10, 20, 30, 40]
a: Any = I(1)
t = I(2)
print(xs[t], xs[t:], xs[:a], xs[a:t], "ab" * t, list(range(t)), hex(t), "%d %x" % (t, t))
mixed: list[Any] = [1, "two", 3.0]
print(mixed[t], mixed[:t])
