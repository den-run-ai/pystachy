# pystachy: dynamic-any
from dataclasses import dataclass
from typing import Any, NamedTuple
from typed_fields import Imported


@dataclass
class Record:
    n: int
    f: float = float("nan")


class Pair(NamedTuple):
    n: int
    f: float


class Failure(Exception):
    def __init__(self) -> None:
        self.n: int = int("1000")
        super().__init__("bad")


class Detailed(Failure):
    def __init__(self) -> None:
        super().__init__()
        self.f: float = float("nan")


class Generic:
    def __init__(self, n) -> None:
        self.n = n


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def run() -> None:
    r = Record(int("1000"))
    same("dataclass int", r.n, r.n)
    same("dataclass float", r.f, r.f)
    print("record repr", repr(r))
    p = Pair(int("1000"), float("nan"))
    same("named tuple int", p.n, p.n)
    same("named tuple float", p.f, p.f)
    same("named tuple index", p[0], p.n)
    q = p._replace(n=int("2000"))
    same("replace repeated", q.f, q.f)
    print("tuple repr", repr(q))
    print("tuple fields", p._fields)
    try:
        raise Detailed()
    except Failure as e:
        same("exception int", e.n, e.n)
        print("exception repr", repr(e))
    g = Generic(int("1000"))
    same("specialized int", g.n, g.n)
    h = Generic(float("nan"))
    same("specialized float", h.n, h.n)
    imported = Imported()
    same("imported field", imported.n, imported.n)
    same("imported default", imported.default, Imported.default)
    old: Any = imported.n
    imported.rebind()
    same("imported replacement", old, imported.n)


run()
