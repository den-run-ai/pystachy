# pystachy: dynamic-any
# A comparison method whose parameter is annotated with a class runs with an object of the class,
# of a subclass, or None, through Any values. With a value of another type, which its body is not
# compiled for, the comparison gives what the method gives here, as one that declines the value:
# False for ==, True for != (without __ne__, as object.__ne__ inverts __eq__) and the ordering's
# TypeError, without the other operand's method, which CPython does not run either. A NamedTuple's
# != is tuple's, also where its class defines __eq__ (#772).
from typing import Any, NamedTuple


class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other: "Point") -> bool:
        return isinstance(other, Point) and self.x == other.x

    def __lt__(self, other: "Point") -> bool:
        if not isinstance(other, Point):
            raise TypeError(f"'<' not supported between instances of 'Point' and '{type(other).__name__}'")
        return self.x < other.x


class Point3(Point):
    def __init__(self, x: int, z: int) -> None:
        super().__init__(x)
        self.z = z


class Wild:
    def __eq__(self, other: Any) -> bool:
        return True


class Pair(NamedTuple):
    a: int
    b: int

    def __eq__(self, other: "Pair") -> bool:
        return isinstance(other, Pair) and self.a == other.a


p: Any = Point(1)
q: Any = Point(1)
r: Any = Point3(1, 2)
one: Any = 1
s: Any = "1"
none: Any = None
w: Any = Wild()
print(p == q, p != q, p == r, r == p, p == none, p != none, none == p)
print(p == one, one == p, p != one, one != p, p == s, s == p)
print(p in [one, s, q], [one, s].count(p), [one, p].index(p), p in (one, s))
print({"k": p} == {"k": q}, {"k": p} == {"k": "1"}, [p, 1] == [q, 1], [p] == [one])
print(w == p, p == w, p != w, w != p)
print(p < Point(2), Point(0) < p)
for x in [one, s]:
    try:
        print(p < x)
    except TypeError as err:
        print("TypeError:", err)
t: Any = Pair(1, 2)
u: Any = Pair(1, 3)
pt: Any = (1, 2)
print(t == u, t != u, t == pt, pt == t, t != pt, pt != t, t == one, t != one)
