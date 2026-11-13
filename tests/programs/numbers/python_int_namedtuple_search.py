# A tuple's in, count() and index() find NamedTuples of promoting ints as == compares them: also
# where the item or the value sought may be None (a parameter's NamedTuple, or one annotated
# NT | None), whose fields keep their values past 64 bits (#1439)
# pystachy: python-int
from typing import NamedTuple


class NT(NamedTuple):
    a: int
    b: int


def where(t: tuple[NT, NT], x: NT) -> str:
    try:
        return str(t.index(x))
    except ValueError as e:
        return str(e)


def given(n: NT, m: NT) -> None:
    print("given", n in (m,), m in (n,), NT(n.a, n.b) in (m,), n in (NT(m.a, m.b),), (m, n).count(n), where((m, n), n), where((m, m), NT(n.a, 7)))


def maybe(x: NT | None, y: NT | None) -> None:
    print("maybe", x in (y,), y in (x,), x not in (y,), (y, x).count(x), (x, y).count(y), (x, y).index(y))


def fresh(x: NT | None, a: int) -> None:
    print("fresh", NT(a, 2) in (x,), x in (NT(a, 2),), (x, x).count(NT(a, 2)), (NT(a, 2), x).index(x))


def against_tuple(n: NT, t: tuple[int, int]) -> None:
    print("tuple", t in (n,), n in (t,), (t, n).count(t), (n, t).count(n))


def same(n: NT) -> None:
    print("same", n in (n,), (n, n).count(n))


big = 2 ** 70
for v in [1, 2 ** 62, 2 ** 63, big, -big]:
    given(NT(v, 2), NT(v, 2))
    given(NT(v, 2), NT(v + 1, 2))
    maybe(NT(v, 2), NT(v, 2))
    maybe(NT(v, 2), NT(v, 3))
    maybe(NT(v, 2), None)
    maybe(None, NT(v, 2))
    fresh(NT(v, 2), v)
    fresh(NT(v, 2), v + 1)
    fresh(None, v)
    against_tuple(NT(v, 2), (v, 2))
    against_tuple(NT(v, 2), (v, 3))
    same(NT(v, 2))
maybe(None, None)
