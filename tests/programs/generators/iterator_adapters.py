# Native adapters share their cursor across iter(), next() and consumers.
from typing import Iterable


def twice(x: int) -> int:
    return x * 2


def add(a: int, b: int, c: int) -> int:
    return a + b + c


def odd(x: int) -> bool:
    return x % 2 != 0


def total(xs: Iterable[int]) -> int:
    return sum(xs)


z = zip([1, 2, 3], ["a", "b", "c"])
print(iter(z) is z, next(z), list(z), list(z))
e = enumerate([4, 5], start=7)
print(iter(e) is e, next(e), list(e), list(e))
m = map(twice, [3, 4])
print(iter(m) is m, next(m), list(m), list(m))
many = map(add, [1, 2], [3, 4], [5, 6])
print(next(many), list(many))
f = filter(odd, [0, 1, 2, 3, 4])
print(iter(f) is f, next(f), list(f), list(f))
truth = filter(None, [0, 1, 0, 2])
print(next(truth), list(truth))
r = reversed([4, 5, 6])
print(iter(r) is r, next(r), list(r), list(r))
s = reversed("aé🐍")
print(list(s))
t = reversed((1, 2, 3))
print(list(t))
b = reversed(b"abc")
print(list(b))
numbers = reversed(range(1, 8, 2))
print(next(numbers), list(numbers))
empty = zip()
print(list(empty))
one = zip([1, 2])
print(list(one))
print(list(enumerate(zip([1, 2], [3, 4]))))
print(list(zip(enumerate([4, 5]), reversed([6, 7]))))
print(total(map(twice, [1, 2, 3])))
g = (x + 1 for x in [1, 2])
print(iter(g) is g, list(iter(g)))

print(type(z).__name__, type(e).__name__, type(m).__name__, type(f).__name__)
print(type(truth).__name__, type(r).__name__, type(s).__name__, type(t).__name__)
print(type(b).__name__, type(numbers).__name__)
d = {"a": 1, "b": 2}
dr = reversed(d)
print(type(dr).__name__, next(dr), list(dr))
raw = iter(b"a\x00z")
print(type(raw).__name__, list(raw))
