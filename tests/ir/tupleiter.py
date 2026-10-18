# tupleiter: a for loop over a tuple of one item type steps through the tuple's slots, below the
# length its type gives. tupleiter.calls pins that these loops build no list (with
# PYSTACHY_OPT=-tupleiter, each would call pys_list_new and pys_list_append for the tuple's items
# first), and that iter() of a tuple in __iter__ still makes the list its iterator steps through.
# Loading the iter helper conservatively enables exception handling, even for this concrete return.
from typing import Iterator

NB = ((0, 1), (1, 0), (0, -1), (-1, 0))


class Bag:
    def __init__(self, t: tuple[str, str]) -> None:
        self.t = t

    def __iter__(self) -> Iterator[str]:
        return iter(self.t)


def total(t: tuple[float, float, float, float]) -> float:
    s = 0.0
    for x in t:
        s += x
    return s


def near(x: float, y: float) -> int:
    n = 0
    for dx, dy in NB:
        if x + dx > 0.0 and y + dy > 0.0:
            n += 1  # (an overflow check: pys_raise)
    return n


def mixed(xs: list[float]) -> float:
    s = 0.0
    for w, x in zip((0.5, 0.25, 0.125), xs):  # (the list's read is unchecked too: listget)
        s += w * x
    for w in reversed((3.0, 4.0)):
        s -= w
    return s
