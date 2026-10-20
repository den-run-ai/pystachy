# sum(o, start) of an object (also of a tuple, a dict or a NamedTuple) iterates it once start is
# evaluated, as sum(xs, start) does a list
from typing import Iterator, NamedTuple


class C:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __iter__(self) -> Iterator[int]:
        print("iter")
        return iter(self.xs)


class P(NamedTuple):
    a: int
    b: int


def st() -> int:
    print("start")
    return 10


print(sum(C(), 10), sum(C(), 1.5), sum(C(), st()), sum((1, 2), 3), sum({1: 2, 3: 4}, 5), sum(P(1, 2), 4), sum(C(), int(True)))
