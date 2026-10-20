# pystachy: dynamic-any
# An object and a value of another type, or an object of an unrelated class, compare through Any
# values as CPython's rich comparison runs them (#772): the left operand's method, else the right
# operand's reflected one (a builtin type's own method declines an object), else identity for ==
# and != and TypeError for an ordering; != without __ne__ is not __eq__. So do a container's
# search and a dict's lookup, which compare its items with the value.
from typing import Any


class E:
    def __eq__(self, other: object) -> bool:
        print("E.eq", type(other).__name__)
        return True

    def __ne__(self, other: object) -> bool:
        print("E.ne", type(other).__name__)
        return False

    def __hash__(self) -> int:
        return 1


class OnlyEq:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: Any) -> bool:
        return other == self.v


class A:
    def __init__(self, v: int) -> None:
        self.v = v

    def __lt__(self, other: Any) -> bool:
        return self.v < other.v

    def __ge__(self, other: Any) -> bool:
        return self.v >= other.v


class B:
    def __init__(self, v: int) -> None:
        self.v = v


class P:
    pass


def order(what: str, a: Any, b: Any) -> None:
    try:
        if what == "<":
            print(a < b)
        elif what == ">":
            print(a > b)
        elif what == "<=":
            print(a <= b)
        else:
            print(a >= b)
    except (TypeError, AttributeError) as err:
        print(type(err).__name__ + ":", err)


e: Any = E()
n: Any = 1
s: Any = "s"
f: Any = 2.5
none: Any = None
xs: Any = [1]
print(e == n, n == e, e != n, n != e)
print(e == s, s == e, f == e, e == none, none == e, xs == e)
print(e in [n], [e].count(n), [n].count(e), [n].index(e), e in (n,), n in [e])
d: dict[Any, Any] = {n: "one"}
print(e in d, d[e], d.get(e, "no"))
d2: dict[Any, Any] = {e: "e"}
print(n in d2, d2[n])
o: Any = OnlyEq(3)
three: Any = 3
four: Any = 4
print(o == three, three == o, o != three, three != o, o == 4, o in [three], [four, three].index(o))
a: Any = A(1)
b: Any = B(2)
print(e == a, a == e, e != a, a != e)
print(a < b, b > a, a >= b, b <= a)
order("<", b, a)
order(">", a, b)
order("<=", a, b)
order(">=", b, a)
p: Any = P()
q: Any = P()
print(p == q, p != q, p == p, p == 1, 1 != p, p in [1, q], [q, 1].count(p))
order("<", p, 1)
order("<", 1, a)
order(">", "s", a)
