# Objects inside lists, dicts and tuples: ==, in, index, sorting and repr go through __eq__/__lt__/__repr__
from dataclasses import dataclass
from typing import Optional


@dataclass
class P:
    x: int
    y: int


class Tok:
    def __init__(self, k: str, n: int):
        self.k = k
        self.n = n

    def __lt__(self, o: "Tok") -> bool:
        return self.n < o.n

    def __eq__(self, o: "Tok") -> bool:
        return self.k == o.k

    def __repr__(self) -> str:
        return f"Tok({self.k!r}, {self.n})"


class Plain:
    def __init__(self):
        self.v = 1


@dataclass
class Tree:
    val: int
    kids: list["Tree"]


pts = [P(1, 2), P(3, 4)]
print(pts, P(1, 2) in pts, P(9, 9) in pts, pts.index(P(3, 4)), pts.count(P(1, 2)), pts == [P(1, 2), P(3, 4)])
toks = [Tok("b", 3), Tok("a", 1), Tok("c", 2)]
print(sorted(toks), min(toks), max(toks), Tok("a", 99) in toks)
toks.sort()
print(toks, (Tok("x", 1), 2))
d: dict[str, P] = {"a": P(0, 0)}
print(d, d == {"a": P(0, 0)}, {"k": [P(1, 1)]})
opt: list[Optional[P]] = [None, P(5, 5)]
print(opt, None in opt, P(5, 5) in opt)
t = Tree(1, [Tree(2, []), Tree(3, [Tree(4, [])])])
print(t, t == Tree(1, [Tree(2, []), Tree(3, [Tree(4, [])])]))
p = Plain()
s = str(p)
print(s.startswith("<__main__.Plain object at 0x"), repr(p) == s, f"{p}" == s)
print(f"{P(1, 2)}", f"{3:}", f"{True:}", f"{'x':}", repr(None))
pl = [Plain()]
print(pl[0] in pl, Plain() in pl)
