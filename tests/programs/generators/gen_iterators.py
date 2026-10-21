# Generators with iterator objects (#490 with #477): Iterable[T] parameters, a generator over an
# iterator object, iter() and next() of an __iter__ that yields, unpacking, min()/max() with key=,
# yield from an iterator object, an iterator class that steps a generator, PEP 479 in eh mode.
from collections.abc import Iterable, Iterator


class Count:
    def __init__(self, n: int) -> None:
        self.i = 0
        self.n = n

    def __iter__(self) -> "Count":
        return self

    def __next__(self) -> int:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i


class Bag:
    def __init__(self) -> None:
        self.xs = [3, 1, 2]

    def __iter__(self) -> Iterator[int]:
        for x in self.xs:
            yield x


def total(it: Iterable[int]) -> int:
    s = 0
    for x in it:
        s += x
    return s


def gen(n: int) -> Iterator[int]:
    for i in range(n):
        yield i * 10


def through(it: Iterator[int]) -> Iterator[int]:
    # a generator over an iterator object: the loop's StopIteration catch spans its yield
    for x in it:
        yield x + 1


class Wrap:
    # an iterator class whose __next__ steps a generator it holds
    def __init__(self, n: int) -> None:
        self.g = squares(n)

    def __iter__(self) -> "Wrap":
        return self

    def __next__(self) -> int:
        return next(self.g) + 1000


def squares(n: int) -> Iterator[int]:
    for i in range(n):
        yield i * i


def delegate(n: int) -> Iterator[int]:
    yield from Count(n)
    yield from iter([7, 8])
    yield -1


def pairs() -> Iterator[int]:
    it = iter([1, 2, 3])
    yield next(it)
    for x in it:
        yield x * 100


def bad() -> Iterator[int]:
    c = Count(1)
    yield next(c)
    yield next(c)  # StopIteration inside a generator: RuntimeError (PEP 479)


print(total(gen(4)), total(Count(3)), total(Bag()))
print(list(through(Count(3))), list(through(gen(2))))
it = iter(Bag())
print(next(it), next(it), next(it), next(it, -1))
print(tuple(Bag()), min(Bag(), key=lambda v: -v), max(Bag()), 2 in Bag(), 9 in Bag(), 9 not in Bag())
a, b, c = Bag()
print(a, b, c)
x, y = gen(2)
print(x, y)
g = gen(3)
print(next(iter(g)), list(iter(g)))
ci = iter(Count(2))
print(list(through(ci)))
try:
    for v in through(Count(2)):
        print("v", v)
        raise ValueError("body")
except ValueError as e:
    print("caught", e)
print(sum(Bag(), 10), sum(gen(3), 0.5), sorted(Bag()))
print(", ".join(str(v) for v in Bag()))
p, q = gen(2)
print(p, q)
try:
    r1, r2 = gen(3)
except ValueError as e:
    print("err", e)
try:
    s1, s2, s3 = gen(1)
except ValueError as e:
    print("err", e)
h, *rest = gen(4)
print(h, rest)
m1, *mrest = Bag()
print(m1, mrest)
print(list(delegate(2)), list(pairs()))
print(list(Wrap(3)), [w for w in Wrap(2)])
print(list(zip(squares(3), Count(5))), list(enumerate(Count(2))))
for i, v in enumerate(squares(3)):
    print(i, v)
print(sorted(squares(4), key=lambda v: -v), set(squares(3)), max(squares(3)))
print(dict(zip(["a", "b"], squares(2))))
try:
    print(list(bad()))
except RuntimeError as e:
    print("RuntimeError", e)
g = squares(3)
for v in iter(g):
    print("it", v)
    break
print(list(g))
