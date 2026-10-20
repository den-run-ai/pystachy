# pystachy: dynamic-any
# sum() of a generator of Any values adds them as they come, as CPython's sum() does: ints, floats,
# a start, and a class's __add__ and __radd__, whose calls interleave with the generator's (#782).
from typing import Any


class Money:
    def __init__(self, c: int) -> None:
        self.c = c

    def __add__(self, other: Any) -> "Money":
        print("add", type(other).__name__)
        return Money(self.c + (other.c if isinstance(other, Money) else other))

    def __radd__(self, other: Any) -> "Money":
        print("radd", other)
        return Money(self.c + other)


def gen(xs: list[Any]) -> Any:
    for x in xs:
        print("yield", type(x).__name__)
        yield x


rows: list[Any] = [{"t": 3}, {"t": 21.5}, {"t": 18}]
print(sum(r["t"] for r in rows), sum((r["t"] for r in rows), 10), sum(x for x in rows[0].values()))
total = sum(m for m in gen([Money(1), Money(2)]))
print(total.c)
try:
    print(sum(x for x in gen(["a", "b"])))
except TypeError as err:
    print("TypeError:", err)
