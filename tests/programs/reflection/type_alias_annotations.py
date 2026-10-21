# Module-level type aliases name their values in annotations (#121): name = <a type> and
# name: TypeAlias = <a type>, of builtin types, unions, containers, Callable, tuples (also
# runtime-length ones) and other aliases. An alias of int, float, str or bool stays a value
# (Pos("3"), isinstance(x, Pos)); the others only annotations name, and an unused one compiles.
from dataclasses import dataclass
from typing import Callable, Optional, TypeAlias, Union

Pos = int
Score = float
Name = str
Flag = bool
Count = Pos  # an alias of an alias
Row = list[str]
Table = list[Row]
Index: TypeAlias = dict[str, int]
MaybeRow = Optional[Row]
Num = int | float
Cell = Union[int, str, None]
Handler = Callable[[str], int]
Key = tuple[str, ...]
Point = tuple[float, float]
Unused = dict[str, list[frozenset[int]]]


class Node:
    def __init__(self, name: Name, kids: "Nodes") -> None:
        self.name = name
        self.kids = kids

    def size(self) -> Count:
        return 1 + sum(k.size() for k in self.kids)


Nodes = list[Node]
OptNode = Node | None


@dataclass
class Placed:
    at: Pos
    value: Num
    label: Name = "?"


def skip_ws(src: Name, pos: Pos) -> Pos:
    while pos < len(src) and src[pos] == " ":
        pos += 1
    return pos


def total(t: Table) -> Count:
    return sum(len(r) for r in t)


def lookup(ix: Index, k: str) -> MaybeRow:
    if k in ix:
        return [k] * ix[k]
    return None


def apply(h: Handler, s: str) -> int:
    return h(s)


def dotted(k: Key) -> str:
    return ".".join(k)


def mid(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def scale(x: Num, f: Num) -> Num:
    return x * f


def describe(c: Cell) -> str:
    if c is None:
        return "empty"
    if isinstance(c, int):
        return f"int {c}"
    return f"str {c!r}"


def first(n: OptNode) -> str:
    return n.name if n is not None else "-"


def kind(x: int | str | float) -> str:
    # isinstance() reads an alias of int, float, str or bool as that class
    if isinstance(x, Pos):
        return "pos"
    if isinstance(x, (Name, Score)):
        return "name-or-score"
    return "other"


def count_words(lines: Row) -> Count:
    words: Row = []
    for line in lines:
        words.extend(line.split())
    seen: dict[Name, Flag] = {}
    for w in words:
        seen[w] = True
    return len(seen)


def tally() -> Callable[[Row], Count]:
    # (a closure's annotations, and a local's, name aliases too)
    seen: Index = {}

    def add(r: Row) -> Count:
        for w in r:
            seen[w] = seen.get(w, 0) + 1
        return len(seen)

    return add


class Grid:
    cells: Table

    def __init__(self, cells: Table) -> None:
        self.cells = cells
        self.width: Count = len(cells[0]) if cells else 0

    def row(self, i: Pos) -> Row:
        return self.cells[i]


print(skip_ws("   x", 0), total([["a", "b"], ["c"]]))
print(lookup({"x": 2}, "x"), lookup({}, "y"))
print(apply(len, "hello"), dotted(("a", "b", "c")), dotted(()))
print(mid((0.0, 0.0), (1.0, 3.0)))
print(scale(2, 1.5), scale(2, 3), describe(None), describe(7), describe("é"))
tree = Node("root", [Node("a", []), Node("b", [Node("c", [])])])
print(tree.size(), first(tree), first(None))
p = Placed(3, 2.5)
print(p, Placed(1, 2, "ü"))
print(kind(3), kind("a"), kind(2.5), isinstance(True, Pos), isinstance(True, Flag))
print(Pos("41") + 1, Count("12") * 2, Name(5), Score("1e3"), Flag(0))
print(count_words(["a b", "b c", "naïve café"]))
g = Grid([["x", "y"], ["z", "w"]])
print(g.width, g.row(1), Grid([]).width)
handlers: list[Handler] = [len, lambda s: s.count("a")]
print([h("banana") for h in handlers])
t = tally()
print(t(["a", "b"]), t(["b", "ç"]))
