# Slicing a fixed-shape tuple or a NamedTuple with bounds known at compile time (integer
# literals, negative ones, None, True/False or left out): a tuple of the items selected, as
# CPython's slice.indices() clamps the bounds, of whatever types they have; the tuple is
# evaluated before its bounds, and None raises CPython's TypeError (sys.version_info[:2] is one)
from typing import NamedTuple


class Version(NamedTuple):
    major: int
    minor: int
    tag: str


calls: list[str] = []


def made(t: tuple[int, str, float, list[int]]) -> tuple[int, str, float, list[int]]:
    calls.append("made")
    return t


t = (1, "é", 2.5, [3])
print(t[1:3], t[:2], t[2:], t[-2:], t[:-3], t[-1:-3], t[5:], t[-9:1], t[None:None], t[True:])
print(t[0:0], t[:], t[1:-1], t[False:False] == ())
print(made(t)[1:2], calls)
nested = ((1, 2), "x", (3, (4, 5)))
print(nested[::], nested[2:][0][1:], nested[:1] + nested[1:2])
v = Version(3, 13, "final")
print(v[:2], v[1:], v[-1:], v[:2] >= (3, 8), v[:0])
first, second = t[:2]
print(first, second, len(t[1:]), t[1:][2][0])


class Box:
    def __init__(self, items: tuple[str, int, bool]) -> None:
        self.items = items

    def head(self) -> tuple[str, int]:
        return self.items[:2]


print(Box(("a", 1, True)).head(), (lambda p: p[1:])((1, 2, 3)))
maybe: tuple[int, int] | None = (7, 8)
print(maybe[1:])
maybe = None
try:
    print(maybe[1:])
except TypeError as e:
    print("TypeError:", e)
