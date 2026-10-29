# pystachy: dynamic-any
# Methods whose bodies only compute with numbers, their receiver's plain fields and locals
# holding its bytes fields: their unreturned numeric arguments need no boxes, and a local
# sharing a field's object keeps sharing it across such calls (the call runs no other code).
from typing import Any


class Cursor:
    def __init__(self, text: bytes) -> None:
        self.data = text
        self.pos = 0
        self.n = len(text)
        self.limit = int("5000")

    def end_of(self, begin: int) -> int:
        data = self.data
        n = len(data)
        i = begin
        while i < n and data[i] != 32:
            i += 1
        return i

    def same_arg(self, a: int) -> int:
        return a

    def via(self, a: int) -> int:
        b = a
        return b

    def at(self) -> int:
        return self.pos

    def capped(self, a: int) -> int:
        if a > self.limit:
            return self.limit
        return a

    def moved(self, a: int) -> None:
        self.pos = a


class Base:
    def __init__(self) -> None:
        self.pos = int("2000")

    def keep(self, a: int) -> int:
        return a + 0


class Derived(Base):
    def keep(self, a: int) -> int:
        return a


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, a == b)


def shared(c: Cursor) -> int:
    # (one local sharing c.pos: it keeps sharing across proven calls)
    begin = c.pos
    end = c.end_of(begin)
    same("begin is pos", begin, c.pos)
    same("end", end, end)
    print("end at", end, c.data[end:end + 4])
    r = c.same_arg(begin)
    same("returned parameter", r, begin)
    same("returned parameter field", r, c.pos)
    return end


def field_result(c: Cursor) -> None:
    q = c.pos
    t = c.at()
    same("field local and result", q, t)


def stored(c: Cursor, before: Any, to: int) -> None:
    w = c.pos
    c.moved(to)
    same("stored by a method", w, c.pos)
    x: Any = w
    same("kept object", x, before)


def run(c: Cursor) -> None:
    c.pos = int("300")
    end = shared(c)
    v = c.via(end)
    same("returned alias", v, end)
    p = c.at()
    same("returned field", p, c.pos)
    field_result(c)
    big = int("6000")
    k = c.capped(big)
    same("capped", k, c.limit)
    small = int("10") + 1
    k2 = c.capped(small)
    same("capped argument", k2, small)
    m = int("777") + 1
    c.end_of(m)
    a: Any = m
    b: Any = m
    same("unobserved argument", a, b)
    c.pos = int("300") + 1
    stored(c, c.pos, int("4000"))


def dispatch(o: Base) -> None:
    n = o.pos
    r = o.keep(n)
    same("dispatched", r, n)


run(Cursor(b"x" * 300 + b"word rest"))
dispatch(Base())
dispatch(Derived())
