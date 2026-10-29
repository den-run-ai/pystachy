# pystachy: python-int
# sum(), min() and max() in a module that opts in: sums pass 64 bits as CPython's do, from
# generator expressions, ranges, generators, iterators, map() and lists, with every start
from typing import Iterator


def squares(n: int) -> Iterator[int]:
    for i in range(n):
        yield i * i


class Count:
    def __init__(self, n: int) -> None:
        self.n = n
        self.i = 0

    def __iter__(self) -> "Count":
        return self

    def __next__(self) -> int:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i * 2 ** 62


big = 2 ** 64
five: int = 5
print(sum(i * i for i in range(10)))
print(sum(i * 2 ** 40 for i in range(2 ** 24, 2 ** 24 + 4)))
print(sum(i * big for i in range(5)), sum((i * big for i in range(5)), -big))
print(sum((i for i in range(3)), big), sum(x for x in [2 ** 62, 2 ** 62, -(2 ** 62), -(2 ** 62)]))
print(sum(range(-2 ** 63, -2 ** 63 + 3)), sum(range(2 ** 62, 2 ** 62 + 4)))
r = range(2 ** 62, 2 ** 62 + 3)
print(sum(r), sum(r, big))
print(sum(squares(4)), sum(squares(4), big))
print(sum(Count(4)), sum(Count(4), big))
print(sum(map(lambda x: x * big, [1, 2, 3])))
xs = [2 ** 62, 2 ** 62, 2 ** 62, -5]
print(sum(xs), sum(xs, big), sum(xs, -big * big))
print(sum([2 ** 62, 2 ** 62, -(2 ** 62), -(2 ** 62)]), sum([True, True, False], big))
print(sum((2 ** 62, 2 ** 62), 0), sum({2 ** 62: 1, 2 ** 62 + 1: 2}, 1), sum({2 ** 62, 2 ** 62 + 1}))
e: list[int] = []
print(sum(e), sum(e, big), sum(e, five))
print(sum(x * 1.5 for x in range(4)), sum((x * 0.5 for x in range(4)), 3), sum((x * 0.5 for x in range(4)), five))
print(sum([0.1, 0.2, 0.3], 1), sum([0.5, 0.25], five))
s = sum(i for i in range(3))
print(s + 2 ** 63, type(s).__name__)
print(max(i * big for i in range(-2, 3)), min(i * big for i in range(-2, 3)))
print(max(-big, big * 2, 7), min(x - big for x in [5, 1, 9]))
print(max(i * i for i in range(5)), min(range(-3, 3)))
try:
    max(i * big for i in range(0))
except ValueError as ex:
    print("ValueError:", ex)
