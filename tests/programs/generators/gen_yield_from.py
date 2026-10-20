# yield from (#490, PEP 380): delegation to another generator (whose return value is the value
# of yield from), and yield from a list, str, tuple, dict, set, generator expression or an
# object whose __iter__ yields.
from collections.abc import Generator, Iterator


def inner(n: int) -> Iterator[int]:
    for i in range(n):
        yield i


def parse(items: list[str]) -> Generator[int, None, str]:
    for s in items:
        if not s.isdigit():
            return "stopped at " + s
        yield int(s)
    return "all digits"


def driver(items: list[str]) -> Generator[int, None, None]:
    reason = yield from parse(items)
    print("inner said:", reason)
    yield -1


def counted(n: int) -> Generator[int, None, int]:
    yield from inner(n)
    return n * 100


def total(parts: list[int]) -> Iterator[int]:
    s = 0
    for p in parts:
        got: int = yield from counted(p)
        s += got
    yield s


class Bag:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        yield from self.xs


def outer() -> Iterator[int]:
    yield -1
    yield from inner(3)
    yield from [10, 20]
    yield from (x * 100 for x in range(2))
    yield from (10, 11)
    yield from {7: "a", 8: "b"}
    yield from Bag([5, 6])
    yield 99


def letters(s: str):
    yield from s
    yield from sorted({"z", "y"})


def deep(n: int) -> Iterator[int]:
    if n > 0:
        yield from deep(n - 1)
    yield n


print(list(outer()))
for v in outer():
    if v == 1:
        break
    print(v)
print(list(driver(["1", "2", "x", "3"])), list(driver(["4"])))
print(list(total([1, 2])))
print(list(letters("ab")))
print(list(deep(5)), sum(deep(200)))
