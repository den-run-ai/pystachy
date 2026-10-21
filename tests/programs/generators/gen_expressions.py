# Generator expressions as values (#490): anonymous generators, never lists. The first iterable
# is evaluated where the expression is, the rest lazily as the generator runs; a global is read
# then (late binding); the function's own variables it reads keep their values.
from collections.abc import Iterator


def trace(x: int) -> int:
    print("  eval", x)
    return x


def evens(xs: list[int]) -> Iterator[int]:
    return (x for x in xs if x % 2 == 0)


def scaled(xs: list[int], k: int) -> list[int]:
    g = (x * k for x in xs)
    return list(g)


scale = 10
g = (x * scale for x in [trace(1), trace(2)])
print("made")
scale = 100
print(next(g))
scale = 1000
print(list(g), list(g))
squares = (x * x for x in range(5))
print(next(squares), sum(squares), sum(squares))
print(list(evens([1, 2, 3, 4])), scaled([1, 2], 3))
lazy = (trace(y) for y in [7, 8])
print("lazy made")
for v in lazy:
    print("got", v)
print(tuple(x + 1 for x in [1, 2]), next((w for w in ["a", "b"] if w > "a"), "none"), next((w for w in ["a"] if w > "z"), "none"))
pairs = ((i, c) for i, c in enumerate("xy"))
print(list(pairs))
