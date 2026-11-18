# == and != of NamedTuples of promoting ints, compared as tuples of their fields: also where one
# may be None (a parameter's or a field's NamedTuple, or one annotated NT | None), whose fields
# keep their values past 64 bits (#1439)
# pystachy: python-int
from typing import NamedTuple


class NT(NamedTuple):
    a: int
    b: int


class Mixed(NamedTuple):
    n: int
    s: str
    p: tuple[int, int]


class Box:
    def __init__(self, nt: NT | None) -> None:
        self.nt = nt


def given(n: NT, m: NT) -> None:
    print("given", n == m, m == n, n != m, n == NT(n.a, n.b), NT(n.a, n.b) == n, n != NT(n.a, 0))


def maybe(x: NT | None, y: NT | None) -> None:
    print("maybe", x == y, y == x, x != y, y != x)


def against_tuple(n: NT, t: tuple[int, int]) -> None:
    print("tuple", n == t, t == n, n != t, t != n)


def nested(n: NT, m: NT) -> None:
    print("nested", [n] == [m], (n,) == (m,), (n, 1) == (m, 1), {1: n} == {1: m}, [n, m] == [m, n])


def mixed(x: Mixed, y: Mixed | None) -> None:
    print("mixed", x == y, y == x, x != y)


def from_field(b: Box, n: NT) -> None:
    print("field", b.nt == n, n == b.nt, b.nt != n)


big = 2 ** 70
for v in [1, 2 ** 62, 2 ** 63, big, -big]:
    given(NT(v, 2), NT(v, 2))
    given(NT(v, 2), NT(v + 1, 2))
    maybe(NT(v, 2), NT(v, 2))
    maybe(NT(v, 2), NT(v, 3))
    maybe(NT(v, 2), None)
    maybe(None, NT(v, 2))
    against_tuple(NT(v, 2), (v, 2))
    against_tuple(NT(v, 2), (v, 3))
    nested(NT(v, 2), NT(v, 2))
    nested(NT(v, 2), NT(v, 1))
    mixed(Mixed(v, "s", (v, 1)), Mixed(v, "s", (v, 1)))
    mixed(Mixed(v, "s", (v, 1)), Mixed(v, "s", (v, 2)))
    mixed(Mixed(v, "s", (v, 1)), None)
    from_field(Box(NT(v, 2)), NT(v, 2))
    from_field(Box(None), NT(v, 2))
maybe(None, None)
print(max([NT(big, 1), NT(big, 2)]) == NT(big, 2), sorted([NT(big + 1, 0), NT(big, 5)])[0] == NT(big, 5))
