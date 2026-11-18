# math.prod() with a str start over items of a union that holds objects, where an item is None:
# CPython's TypeError for that item, after the items before it multiplied the start. A union of
# classes, and one of objects and ints, holds None as a null box, which no tag test may read
import math


class R:
    def __rmul__(self, other: str) -> str:
        return other + "!"


class S:
    def __rmul__(self, other: str) -> str:
        return other + "?"


def mixed(f: int) -> int | R:
    if f == 0:
        return 2
    if f == 1:
        return R()
    return None


def classes(f: int) -> R | S:
    if f == 0:
        return R()
    if f == 1:
        return S()
    return None


for picks in [[0, 1], [0, 2, 1], [2]]:
    xs: list[int | R] = [mixed(f) for f in picks]
    try:
        print(math.prod(xs, start="ab"))
    except TypeError as e:
        print("TypeError", e)
for picks in [[0, 1], [1, 2, 0]]:
    ys: list[R | S] = [classes(f) for f in picks]
    try:
        print(math.prod(ys, start="cd"))
    except TypeError as e:
        print("TypeError", e)
