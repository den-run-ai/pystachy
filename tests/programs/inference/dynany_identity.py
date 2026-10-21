# pystachy: dynamic-any
# `is` and id() of Any values agree (#797): two values are one object exactly where their ids are
# equal, as CPython's. An int is its own object: one per value from -5 to 256, as CPython caches
# those, and one per value for an int literal, as CPython's equal constants are one object; an
# int computed at run time is a new object, as int("1000") is in CPython. Floats, strs,
# containers, objects and functions keep their identity.
from typing import Any


class Obj:
    def m(self) -> int:
        return 1


def both(label: str, a: Any, b: Any) -> None:
    # (both are alive here, held by the arguments, as CPython's ids are compared only then)
    print(label, a is b, a is not b, id(a) == id(b))


def thousand() -> Any:
    return 1000


def run() -> None:
    a: Any = 1000
    both("literal, computed", a, int("1000"))
    c: Any = int("1000")
    d = c
    both("one computed int, two names", c, d)
    both("two computed ints", int("1000"), int("1000"))
    both("literal, literal", a, 1000)
    both("literal, another function's literal", a, thousand())
    both("literal, sum", a, 999 + int("1"))
    both("small ints", int("100"), int("100"))
    both("-5", int("-5"), -5)
    both("256", int("256"), 256)
    both("257", int("257"), 257)
    both("-6", int("-6"), -6)
    both("max, computed twice", int("9223372036854775807"), int("9223372036854775807"))
    both("max, literal twice", 9223372036854775807, 9223372036854775807)
    xs: list[Any] = []
    for _ in range(3):
        xs.append(1000)
    both("a literal appended twice", xs[0], xs[1])
    f: Any = float("1.5")
    g = f
    both("one float, two names", f, g)
    both("two computed floats", float("1.5"), float("1.5"))
    s: Any = "x" * 3
    t: Any = "".join(["x", "x", "x"])
    both("two equal strs", s, t)
    u = s
    both("one str, two names", s, u)
    ys: Any = [1, 2]
    zs = ys
    both("one list, two names", ys, zs)
    both("two equal lists", ys, [1, 2])
    tu: Any = (1, int("2"))
    tv = tu
    both("one tuple, two names", tu, tv)
    o: Any = Obj()
    p = o
    both("one object, two names", o, p)
    both("two objects", o, Obj())
    m1 = o.m
    m2 = o.m
    both("one bound method", m1, m1)
    both("two bound methods", m1, m2)
    fn: Any = thousand
    both("one function", fn, thousand)
    both("None", None, None)
    both("True", True, 1 == 1)
    both("True, 1", True, 1)
    both("1, 1.0", 1, 1.0)


run()
