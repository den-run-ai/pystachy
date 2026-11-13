# "format" % t of a NamedTuple t of promoting ints, whose fields are the arguments: also where it
# may be None (a parameter's NamedTuple, or one annotated NT | None), whose fields keep their
# values past 64 bits (#1439)
# pystachy: python-int
from typing import NamedTuple


class NT(NamedTuple):
    a: int
    b: int


def given(n: NT) -> None:
    print("%d %d" % n, "%x|%s" % n, "%r, %r" % n)


def maybe(x: NT | None) -> None:
    try:
        print("%s %s" % x)
    except TypeError as e:
        print("TypeError:", e)


def single(x: NT | None) -> None:
    try:
        print("[%s]" % x)
    except TypeError as e:
        print("TypeError:", e)


big = 2 ** 70
for v in [1, 2 ** 63, big, -big]:
    given(NT(v, 2))
    maybe(NT(v, 2))
    single(NT(v, 2))
maybe(None)
single(None)
