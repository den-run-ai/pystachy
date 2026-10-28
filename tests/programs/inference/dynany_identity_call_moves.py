# pystachy: dynamic-any
# New numbers passed to calls, call results stored into variables and fields, and a variable's
# last read handed to a call or a copy keep one object per Python value: the callee or the new
# binding boxes it where it first crosses into Any, and a variable still read later shares it.
from typing import Any, Callable


class Holder:
    def __init__(self) -> None:
        self.n = int("1000")


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, a == b)


def keep(v: int) -> Any:
    a: Any = v
    b: Any = v
    same("param crossings", a, b)
    return a


def keep2(v: int, w: int) -> Any:
    a: Any = v
    b: Any = w
    same("two params", a, b)
    return b


def make(n: int) -> int:
    return n + int("1000")


def from_field(h: Holder) -> int:
    return h.n


def widen(v: int, flag: bool) -> Any:
    first: Any = v
    if flag:
        v = first
    second: Any = v
    return first is second


def fresh_args(h: Holder) -> None:
    r = keep(int("1000") + 1)
    same("fresh result", r, r)
    m = int("2000") + 1
    r = keep(m)
    s: Any = m
    same("still read", r, s)
    q = keep(m + 0)
    same("new value", q, s)


def stored_results(h: Holder) -> None:
    x = make(5)
    a: Any = x
    b: Any = x
    same("stored result", a, b)
    y = from_field(h)
    c: Any = y
    same("result of field", c, h.n)
    p = q = make(6)
    same("chained", p, q)
    h.n = make(7)
    d: Any = h.n
    same("field result", d, h.n)


def last_reads(h: Holder) -> Any:
    m = make(8)
    k = keep(m)
    t = make(9)
    u = t
    e: Any = u
    same("copy of last read", e, u)
    v = make(10)
    w = v
    f: Any = w
    g: Any = v
    same("copy still read", f, g)
    z = make(11)
    same("again in call", keep2(z, z), z)
    h.n = make(12)
    n2 = h.n
    keep(n2)
    same("field local passed", n2, h.n)
    return k


def indirect(h: Holder) -> None:
    f: Callable[[int], Any] = keep
    r = f(int("3000") + 1)
    same("indirect fresh", r, r)
    m = int("3000") + 2
    r = f(m)
    s: Any = m
    same("indirect still read", r, s)


fresh_args(Holder())
stored_results(Holder())
k = last_reads(Holder())
print("last read result", k == 1008)
indirect(Holder())
print("widened", widen(int("4000") + 1, False), widen(int("4000") + 2, True))
