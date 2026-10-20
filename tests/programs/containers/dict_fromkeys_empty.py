# dict.fromkeys() of an empty tuple or an empty {} display, which have no item to type: the keys'
# type is the one the dict is wanted with (an annotation, a return type, a parameter's)
from typing import NamedTuple


class Point(NamedTuple):
    x: int
    y: int


def counts() -> dict[str, int]:
    return dict.fromkeys((), 0)


def first(d: dict[tuple[int, str], float]) -> int:
    return len(d)


s: dict[str, int] = dict.fromkeys((), 1)
t: dict[tuple[int, str], float] = dict.fromkeys((), 0.5)
i: dict[int, int] = dict.fromkeys((), 1)
n: dict[str, bool | None] = dict.fromkeys(())
o: dict[str, list[int]] = dict.fromkeys([], [])
e: dict[tuple[int, str], int] = dict.fromkeys({}, 0)
print(s, t, i, n, o, e, counts(), first(dict.fromkeys((), 2.5)), dict.fromkeys((), 3))
s["a"] = 2
t[(1, "x")] = 1.5
i[7] = 8
n["k"] = None
o["l"] = [1]
e[(2, "y")] = 3
c = counts()
c["z"] = 26
print(s, t, i, n, o, e, c)
# the same with items: the iterable's items are the keys
s2: dict[str, int] = dict.fromkeys(("a", "b"), 1)
t2: dict[tuple[int, str], float] = dict.fromkeys(((1, "x"),), 0.5)
print(s2, t2, dict.fromkeys(Point(1, 2), "p"), dict.fromkeys({"x": [1]}, 3))
