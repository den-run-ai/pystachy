# pystachy: python-int
# Promoting ints (docs/python-int.md) in an int | None: variables, parameters, returns, defaults,
# fields, class attributes, globals and closure cells hold values past 64 bits, also where a join
# makes one (x if c else None, x or None), in each spelling of the type, and compare, print, format,
# hash, test and narrow as CPython's do.
from typing import Optional, Union


class Acc:
    seen: int | None = None

    def __init__(self, start: Optional[int] = None) -> None:
        self.cur = start
        self.best: Union[int, None] = None

    def add(self, v: int) -> None:
        self.cur = v if self.cur is None else self.cur + v
        if self.best is None or self.cur > self.best:
            self.best = self.cur

    def value(self) -> int | None:
        return self.cur


class Half(Acc):
    def value(self) -> int | None:
        return None if self.cur is None else self.cur // 2


LAST: None | int = None


def keep(v: int | None) -> None:
    global LAST
    LAST = v


def pick(c: bool, v: int) -> int | None:
    return v if c else None


def first(xs: list[int], d: int | None = 2 ** 70) -> int | None:
    return xs[0] if xs else d


def digits(v: int | None) -> int:
    n = 0
    while v is not None:
        v = v // 10 ** 6 if v >= 10 ** 6 else None
        n += 1
    return n


def counter(start: int | None):
    cur = start

    def step() -> int | None:
        nonlocal cur
        if cur is not None:
            cur = cur * 3
        return cur
    return step


def twice(v: int | None) -> int:
    assert v is not None
    return v * 2


def show(x: int | None, v: int) -> None:
    print(x, repr(x), str(x), f"{x}|{x!r}|{x:>25}|{x:,}", "%s %r" % (x, x), format(x, "x"))
    print(x == v, v == x, x != v, x == None, x is None, x is not None, x == pick(True, v), x == pick(False, v))
    print(x < v + 1, x >= v, max(x, 2 ** 64), min(1, x), hash(x) == hash(v), bool(x), not x, x or 7, x and 7)
    if x is not None:
        y = x
        y += 1
        print(x - v, -x, abs(x), x // 3, y, isinstance(x, int), type(x).__name__)
    print(x in (5, v), x in (1, 2), x in [1, 2], x in {1: 1}, x not in (5, 6))


for v in (2 ** 70, -2 ** 70, 2 ** 64, 2 ** 63, 2 ** 63 - 1, -2 ** 63, -2 ** 63 - 1, 5, 0):
    print("--", v)
    show(v, v)
    x: int | None = v
    w = None if v == 0 else v
    z = pick(v > 0, v) or None
    keep(w)
    print(x, w, z, LAST, first([]), first([], v), first([3], v), digits(v if v > 0 else -v), twice(x))
    s = counter(w)
    print(s(), s())

none = pick(False, 3)
print(none, repr(none), f"[{none}]", none == None, none is None, bool(none), none or 2 ** 65, hash(none) == hash(None), digits(none))
try:
    print(none < 3)
except TypeError as e:
    print("TypeError:", e)
try:
    print(f"{none:>5}")
except TypeError as e:
    print("TypeError:", e)
a = Acc()
for v in (2 ** 62, 2 ** 62, 2 ** 62, -2 ** 64):
    a.add(v)
h = Half(2 ** 80)
h.add(2 ** 80)
Acc.seen = a.best
print(a.value(), a.best, h.value(), Half().value(), Acc.seen, a.seen)
