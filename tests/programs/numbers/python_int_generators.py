# pystachy: python-int
# Generators that yield and return ints past 64 bits: for loops, next(), unpacking, yield from,
# send(), throw(), generator expressions and a module that does not opt in (fixed_iter).
from typing import Generator, Iterator

from fixed_iter import count_up, total


def fib():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b


def powers(n: int) -> Iterator[int]:
    for k in range(n):
        yield 2 ** (60 + k)


def mixed():
    yield 2 ** 64
    for i in range(-2 ** 63, -2 ** 63 + 2):
        yield i
    yield 7
    yield -(2 ** 70)


def squares(n: int) -> Generator[int, None, int]:
    yield n
    return n * n


def outer(n: int):
    r = yield from squares(n)
    yield r
    yield from powers(2)
    yield from (x * 3 for x in [2 ** 63, 1])
    yield from range(2)


def accumulate() -> Generator[int, int | None, None]:
    total = 2 ** 64
    while True:
        got = yield total
        if got is not None:
            total += got


def guarded():
    try:
        yield 1
    except ValueError:
        yield 2 ** 80
    yield 3


class Counter:
    def __init__(self, start: int):
        self.start = start

    def up(self, n: int):
        for k in range(n):
            yield self.start + k


for i, f in enumerate(fib()):
    if i == 100:
        print("fib(100):", f)
        break
print(list(powers(6)))
print(list(mixed()))
print(list(outer(2 ** 40)))
g = powers(5)
print(next(g), next(g), sum(g))
h = squares(3)
print(next(h), next(h, 2 ** 90), next(h, -1))
a, b, c = powers(3)
print(a, b, c, a < b < c)
print(sum(powers(4)), max(powers(4)), min(mixed()), sorted(mixed()))
print(2 ** 62 in powers(4), 2 ** 64 in mixed(), 2 ** 65 in mixed())
acc = accumulate()
print(next(acc), acc.send(5), acc.send(None))
gd = guarded()
print(next(gd), gd.throw(ValueError("x")), next(gd))
print([x - 2 ** 64 for x in mixed()])
sq = (x * x for x in [2 ** 40, 3, -(2 ** 33)])
print(list(sq))
print(list(Counter(2 ** 64).up(3)))
print(total(count_up(4)), [v * 2 ** 64 for v in count_up(3)])
print(total(x for x in [1, 2, 3]))
for x, y in zip(powers(3), mixed()):
    print(x + y)
