# A NamedTuple is a tuple of its fields wherever tuple's own methods run: %-formatting,
# comparisons (with tuples and other NamedTuples too), `in`, iteration, + and *; its class's
# own operator methods run only for the operators they define.
from typing import NamedTuple


class One(NamedTuple):
    s: str


class P(NamedTuple):
    x: int
    y: int


class Q(NamedTuple):
    a: int
    b: int


class Mixed(NamedTuple):
    n: int
    s: str


class ModEq(NamedTuple):
    x: int

    def __eq__(self, other: "ModEq") -> bool:
        return self.x % 10 == other.x % 10


class Rev(NamedTuple):
    x: int

    def __lt__(self, other: "Rev") -> bool:
        return self.x > other.x


class Up(NamedTuple):
    x: int

    def __gt__(self, other: "Up") -> bool:
        return self.x < other.x


class C:
    def __eq__(self, o: "C") -> bool:
        return False


class Holder(NamedTuple):
    c: C
    n: int


# % takes a NamedTuple's fields as its arguments
print("%s" % One("q"), "[%r]" % One("q"), "%d-%d" % P(1, 2), "%s %s" % Mixed(1, "a"))
print("%5d|%-3s|" % Mixed(7, "ab"))

# == and != are tuple's unless the class defines them: __eq__ alone leaves != to tuple's
print(ModEq(1) == ModEq(11), ModEq(1) != ModEq(11), ModEq(1) != ModEq(1))
print(P(1, 2) == P(1, 2), P(1, 2) != P(1, 3), P(1, 2) == Q(1, 2), P(1, 2) != Q(1, 2))
print(P(1, 2) == (1, 2), (1, 2) == P(1, 2), P(1, 2) != (2, 1), Mixed(1, "a") == (1, "a"))

# ordering: the class's own method for its operator, tuple's for the others (never reflected)
print(Rev(1) < Rev(3), Rev(1) > Rev(3), Rev(1) <= Rev(3), Up(1) > Up(3), Up(1) < Up(3))
rs = [Rev(1), Rev(3), Rev(2)]
print(min(rs), max(rs), sorted(rs))
us = [Up(1), Up(3), Up(2)]
print(max(us), min(us), sorted(us), sorted(us, reverse=True))
print(P(1, 2) < Q(1, 3), P(2, 0) > (1, 9), (1, 2) <= P(1, 2), P(1, 2) >= Q(1, 2))

# items compare by identity first, as in a tuple
c = C()
print(Holder(c, 1) == Holder(c, 1), Holder(c, 1) != Holder(c, 1), Holder(c, 1) in [Holder(c, 1)])
print(Holder(C(), 1) == Holder(C(), 1), [Holder(c, 2)].index(Holder(c, 2)), [Holder(c, 3)].count(Holder(c, 3)))

# in, iteration, + and *
p = P(1, 2)
print(2 in p, 3 in p, 3 not in p, "a" in Mixed(1, "a"))
for v in p:
    print(v, end=" ")
print()
print(list(p), sorted(P(3, 1)), sum(p), max(p), ", ".join(One("z")))
print(p + P(3, 4), p + (5,), (0,) + p, p * 2, 2 * p, One("w") * 0, p + p + p)
t = p + (7, 8)
print(t[3], len(t), (1, 2) + (3,), (1, "a") * 2)

# a NamedTuple that may be None
maybe: P | None = None
print(maybe == p, p == maybe, maybe != p, maybe == None)
maybe = P(1, 2)
print(maybe == p, maybe == (1, 2), "%d+%d" % maybe)
print([P(2, 0), maybe].count(None), maybe in [p, None], max(P(1, 2), P(2, 1), P(0, 9)))
maybe = None
print(maybe < p)
