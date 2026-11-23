# Iterator[T] annotations type nothing: a variable they annotate that is assigned iterators of
# two kinds holds Iterator[T].
from typing import Iterator


def gen() -> Iterator[int]:
    yield 3
    yield 4


def local() -> list[int]:
    w: Iterator[int] = iter([6, 7])
    first = next(w)
    w = gen()
    return [first] + list(w)


print(local())
g: Iterator[int] = iter([1, 2])
print(next(g))
g = gen()
print(list(g))
