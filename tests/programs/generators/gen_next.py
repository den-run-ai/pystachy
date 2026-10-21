# next() and iter() of generators (#490): next(g) runs g to its next yield, and raises
# StopIteration once g has finished (it stays finished); next(g, default) gives the default
# instead; iter(g) is g, and iter(o) of an object whose __iter__ yields is the generator it makes.
from collections.abc import Iterator


def numbers(n: int) -> Iterator[int]:
    for i in range(n):
        print("  yield", i)
        yield i


def words() -> Iterator[str]:
    yield "x"
    yield "y"


class Grid:
    def __init__(self, w: int) -> None:
        self.w = w

    def __iter__(self) -> Iterator[tuple[int, int]]:
        for x in range(self.w):
            yield (x, x * x)


def pairwise(g: Iterator[int]) -> Iterator[tuple[int, int]]:
    # the itertools recipe, by next() on the generator it is given
    a = next(g, -1)
    for b in g:
        yield (a, b)
        a = b


g = numbers(3)
print(next(g), next(g))
print(next(g, -1), next(g, -1), next(g, -2))
try:
    print(next(g))
except StopIteration:
    print("StopIteration")
w = words()
print(next(w), next(w, "none"), next(w, "none"))
it = iter(Grid(3))
print(next(it), next(it), list(it))
same = iter(w)
print(same is w, list(pairwise(numbers(4))))
h = numbers(2)
print(h.__next__(), list(h.__iter__()))
