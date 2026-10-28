# pystachy: dynamic-any
# A local that copies a numeric field (i = p.pos) is the field's object, through write-backs
# (p.pos = i), stores to the field, aliases, calls that observe or rebind it, loops and returns,
# in this opt-in module and in a typed module's methods (field_scanner.Scanner).
from typing import Any
from field_scanner import Scanner


class P:
    def __init__(self, start: int) -> None:
        self.pos = start
        self.f = float("nan")


class Bad(Exception):
    def __init__(self, at: int) -> None:
        self.at = at


kept: list[Any] = []


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, a == b or a != a)


def keep(p: P) -> None:
    kept.append(p.pos)


def renew(p: P) -> None:
    p.pos = int(str(p.pos))


def read_then_field(p: P) -> None:
    i = p.pos
    a: Any = i
    b: Any = p.pos
    same("local first", a, b)


def field_then_read(p: P) -> None:
    i = p.pos
    b: Any = p.pos
    a: Any = i
    same("field first", a, b)


def store_ends(p: P, before: Any) -> None:
    i = p.pos
    p.pos = i + 1
    same("after store", i, p.pos)
    same("keeps object", before, i)


def aliased(p: P, q: P, before: Any) -> None:
    i = p.pos
    q.pos = int("7000")
    same("alias local", before, i)
    same("alias field", i, p.pos)


def observed(p: P) -> None:
    i = p.pos
    keep(p)
    same("observed by call", i, kept[-1])


def rebound(p: P) -> None:
    i = p.pos
    renew(p)
    same("rebound by call", i, p.pos)


def write_back(p: P, k: int) -> None:
    i = p.pos
    while k > 0:
        i += 1
        k -= 1
    p.pos = i


def write_back_seen(p: P) -> Any:
    i = p.pos
    i += 5
    p.pos = i
    a: Any = i
    return a


def get(p: P) -> int:
    i = p.pos
    return i


def first_over(p: P, limit: int) -> Any:
    i = 0
    while True:
        i = p.pos
        if i > limit:
            break
        p.pos = i + 100
    a: Any = i
    return a


def check(p: P) -> None:
    i = p.pos
    if i > 0:
        raise Bad(i)


def appended(p: P) -> None:
    xs: list[int] = []
    i = p.pos
    xs.append(i)
    same("appended", xs[0], p.pos)


def two_locals(p: P) -> None:
    i = p.pos
    j = p.pos
    same("two locals", i, j)
    same("two locals field", j, p.pos)


def floats(p: P) -> None:
    x = p.f
    same("nan local", x, p.f)
    p.f = x
    same("nan written back", x, p.f)


def tested(p: P, n: int) -> bool:
    return n < 2


def busy(p: P) -> Any:
    n = 0
    i = 0
    while tested(p, n):
        i = p.pos
        n += 1
    a: Any = i
    return a


def run() -> None:
    p = P(int("1000"))
    read_then_field(p)
    p.pos = int("1001")
    field_then_read(p)
    p.pos = int("1002")
    before: Any = p.pos
    store_ends(p, before)
    p.pos = int("1004")
    before = p.pos
    aliased(p, p, before)
    q = P(int("1005"))
    before = q.pos
    aliased(q, P(0), before)
    p.pos = int("1006")
    observed(p)
    rebound(p)
    p.pos = int("1007")
    before = p.pos
    write_back(p, 0)
    same("unchanged write-back", before, p.pos)
    write_back(p, 3)
    x: Any = p.pos
    y: Any = p.pos
    same("moved write-back", x, y)
    same("moved from before", before, p.pos)
    r = write_back_seen(p)
    same("write-back then local", r, p.pos)
    p.pos = int("1100")
    g: Any = get(p)
    same("returned local", g, p.pos)
    p.pos = int("1200")
    fo = first_over(p, 1150)
    same("loop break", fo, p.pos)
    p.pos = int("1300")
    try:
        check(p)
    except Bad as e:
        same("raised", e.at, p.pos)
    p.pos = int("1400")
    appended(p)
    two_locals(p)
    floats(p)
    p.pos = int("1500")
    b = busy(p)
    same("call in loop test", b, p.pos)
    p.pos = 5
    small: Any = get(p)
    same("small int", small, p.pos)
    p.pos += 1000
    same("augmented", p.pos, p.pos)
    print(len(kept))


def scanner() -> None:
    text = b"alpha" + b" " * int("300") + b"beta  gamma"
    s = Scanner(text, int("0"))
    s.pos = int("5") + int("0")
    start: Any = s.pos
    s.skip()
    after: Any = s.pos
    same("scanner moved", start, after)
    same("scanner read", after, s.pos)
    s.skip()
    same("scanner unchanged", after, s.pos)
    w: Any = s.word()
    same("scanner word", w, after)
    end: Any = s.pos
    pk: Any = s.peek()
    same("scanner peek", pk, end)
    s.skip()
    s.skip()
    print("scanner at", s.pos, text[s.pos:])


run()
scanner()
