# Type aliases, TypeVars and PEP 695 generic classes of another module: from-imported (also
# through a module that re-exports them and makes aliases of them), as module attributes and
# by import *. A from-imported alias of int stays the value it binds (Pos("7")).
import mods.alias_types as at
from mods.alias_reexport import Cells, Coord, Rows, T
from mods.alias_types import Grid, Key, Later, Node, Pair, ParseFloat, Pos, Queue, Row, width
from mods.alias_types import *  # noqa: F403


def skip(src: str, pos: Pos) -> Pos:
    while pos < len(src) and src[pos] == " ":
        pos += 1
    return pos


def names(xs: Later) -> list[str]:
    return [x.name for x in xs]


def parse(f: ParseFloat, s: str) -> float:
    return f(s)


def ends(k: Key) -> Pair[str]:
    return (k[0], k[-1])


def rows(r: at.Row, g: at.Grid[int]) -> int:
    return len(r) + g[0][0]


def count(rs: Rows) -> int:
    return sum(len(r) for r in rs)


def norm(c: Coord) -> int:
    return abs(c[0]) + abs(c[1])


def head(c: Cells[T]) -> T:
    return c[0][0]


def last(xs: list[T]) -> T:
    return xs[-1]


g: Grid[str] = [["a"]]
print(skip("  x", 0), at.origin(), width(["a", "b"]))
print(names([Node("a"), Node("ä")]))
print(parse(float, "1.5"), ends(("a", "b", "c")))
print(rows(["x"], [[2]]), g, count([["a"], ["b", "c"]]), norm((3, -4)))
print(head([[1.5]]), head([["s"]]), last([1, 2]))
r: Row = ["q"]
print(r, Pos("7") * 2, at.Pos(3))
q = Queue("a")
q.put("b")
print(q.take(), q.items)
qi: at.Queue[int] = at.Queue(1)
print(qi.take())
print(origin(), isinstance(1, Pos))  # noqa: F405
