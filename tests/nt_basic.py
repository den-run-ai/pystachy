# typing.NamedTuple classes: positional and keyword construction with defaults, attribute
# reads, methods, _replace, unpacking (also in for loops), constant indexing, len, ==, the
# ordering of tuples, repr (in containers too, and through a cycle) and a module's classes.
from dataclasses import dataclass
from typing import NamedTuple
from mods.records import Pos, Token


class ParsedLine(NamedTuple):
    lineno: int
    section: str | None
    name: str | None
    value: list[str] | None


class Point(NamedTuple):
    """A point with a label."""

    x: int
    y: int = 0
    label: str = "p"

    def norm1(self) -> int:
        return abs(self.x) + abs(self.y)

    def __str__(self) -> str:
        return f"<{self.label} {self.x},{self.y}>"


class Tree(NamedTuple):
    name: str
    kids: list["Tree"]


class Shelf(NamedTuple):
    items: list[str] = []
    owner: "Point | None" = None


lines = [ParsedLine(0, None, None, None), ParsedLine(1, "s", None, None), ParsedLine(2, "s", "k", ["v"])]
for lineno, section, name, value in lines:
    if value is not None:
        value.append("w")
    print(lineno, section, name, value, section is None)
last = lines[-1].value if lines else None
print(last, lines[2], len(lines[2]), lines[2][0], lines[2][-1], lines[0][1] is None)
print(lines, ParsedLine(2, "s", "k", ["v", "w"]) in lines, lines.index(ParsedLine(1, "s", None, None)))

p = Point(3, -4)
q = Point(y=1, x=2, label="q")
print(p, repr(p), str(q), f"{p} {q!r}", p.norm1(), q.label, p == Point(3, -4, "p"), p != q)
a, b, c = q
print(a, b, c, q._replace(), q._replace(label="r", y=7), q)
moved = Pos(3).moved(4)
print(moved, Pos(line=1) < Pos(1, 1), Token("name", None, moved), Token("num", "1", Pos(2, 2)).at.col)
pts = [Point(2, 2), Point(1, 5), Point(2, 1), Point(1, 5, "a")]
print(sorted(pts), min(pts), max(pts), pts[0] > pts[1], pts[1] <= pts[3], sorted(pts, reverse=True)[0])
by_name = {"first": pts[0]}
print(by_name, (p, q), [[p]], {"k": [q]})

s1 = Shelf()
s2 = Shelf()
s1.items.append("shared")
print(s1, s2, s1.items is s2.items, Shelf(["x"], p))
tree = Tree("root", [])
tree.kids.append(Tree("leaf", []))
tree.kids.append(tree)
print(tree, tree.kids[0] < tree, tree == tree._replace())


def find(rows: list[ParsedLine], n: int) -> ParsedLine | None:
    for r in rows:
        if r.lineno == n:
            return r
    return None


hit = find(lines, 2)
miss = find(lines, 9)
print(hit == miss, miss == hit, miss is None, hit is not None and hit.name == "k")
if hit is not None:
    n, s, k, v = hit
    print(n, s, k, v)


@dataclass
class Span:
    name: str
    start: Pos = Pos(1)  # (a NamedTuple is hashable: a dataclass may take one as a default)
    end: Pos = Pos(2, 3)


print(Span("a"), Span("b", Pos(5)), Span("c").start is Span("d").start, Span("a") == Span("a"))
print(len(miss))
