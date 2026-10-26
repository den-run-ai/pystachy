# pystachy: python-int
# Promoting ints (docs/python-int.md) that fit in 64 bits in the storage that keeps 64-bit ints:
# containers, tuples and unions that annotations name (int there is the 64-bit storage type),
# displays and comprehensions, dataclass and NamedTuple fields, and type() of the values.
from dataclasses import dataclass
from typing import NamedTuple, Optional, Union


@dataclass
class Account:
    owner: str
    balance: int = 0


class Point(NamedTuple):
    x: int
    y: int


class Scaled:
    def __init__(self, v: int) -> None:
        self.v = v * 2
        self.neg = -v


def run(n: int) -> int:
    counts: dict[int, int] = {}
    seen: set[int] = set()
    sizes: tuple[int, ...] = (1, 2, 3)
    pair: tuple[int, str] = (n, "x")
    either: int | str = n
    other: Union[int, str] = "y"
    maybe: Optional[int] = None
    for i in range(n):
        counts[i % 3] = counts.get(i % 3, 0) + i * 2 ** 40
        seen.add(i * i)
    keyed = {}
    keyed[n * 3] = 1
    both = {n * 2, n * 5}
    maybe = n * 7
    squares = [i * i * 2 ** 30 for i in range(n)]
    return len(counts) + len(seen) + sum(sizes) + pair[0] + (either if isinstance(either, int) else 0) + len(other) + keyed[n * 3] + len(both) + (maybe if maybe is not None else 0) + squares[-1] // 2 ** 30


print(run(5), run(10))
a = Account("ada", 2 ** 62)
a.balance += 2 ** 62 - 1
p = Point(3, 2 ** 40)
s = Scaled(2 ** 62)
print(a, a.balance + 1, p, p.x * p.y * 2 ** 40, s.v, s.neg)
big = 2 ** 70
one = big // big
print(type(big).__name__, type(one).__name__, type(big) is int, type(one) == int, type(big) is float, big.__class__.__name__)
