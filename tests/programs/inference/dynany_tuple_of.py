# pystachy: dynamic-any
# tuple() of an Any value: a tuple itself, as CPython's tuple() of a tuple is that tuple, else a
# new tuple of the items its iteration gives, with CPython's TypeError for a value without any.
from typing import Any


class Count:
    def __init__(self, n: int) -> None:
        self.n = n

    def __iter__(self) -> Any:
        print("iter")
        return iter(range(self.n))


def gen() -> Any:
    yield "g"
    yield "h"


def show(x: Any) -> None:
    try:
        t = tuple(x)
        print(t, len(t), type(t).__name__)
    except TypeError as error:
        print("TypeError", error)


for value in [[1, 2], "ab", {"k": 1, "j": 2}, (3, 4), Count(3), gen(), [], 5, None]:
    show(value)

held: Any = (1, [2])
again = tuple(held)
print(again is held, again[1] is held[1])
fresh: Any = [1, [2]]
copy = tuple(fresh)
print(copy[1] is fresh[1], copy == (1, [2]))
