# PEP 695 type statements at a module's top level: the value is evaluated lazily, so it may
# name classes and aliases defined further down, or names that never exist if nothing
# evaluates it. An annotation evaluated before the statement runs needs quotes (or
# from __future__ import annotations); one evaluated later, or in a function body, does not.
# A TypeAlias whose value is a string is a forward reference too.
from typing import TypeAlias

type Tree = list[Leaf]  # (Leaf is defined below)
type Twigs = list[Twig]  # (and Twig, an alias of it, bound below)
type Never = dict[str, Missing]  # (never evaluated: Missing is never defined)
type Labels = dict[str, Label]
Label: TypeAlias = "Text"  # (a forward reference to the alias below)
type Text = str
type Matrix[N] = list[list[N]]
type Ints = Matrix[int]


def early(t: "Tree") -> int:
    return len(t)


def first(t: Tree) -> int:
    # (unquoted: the type statement has bound Tree, whose value is evaluated later, if ever)
    return t[0].v


class Leaf:
    def __init__(self, v: int) -> None:
        self.v = v

    def same(self, other: "Leaf") -> bool:
        return self.v == other.v


Twig = Leaf


def twigs(ts: Twigs) -> int:
    return sum(x.v * 10 for x in ts)


def total(t: Tree) -> int:
    acc: int = 0
    for leaf in t:
        acc += leaf.v
    return acc


def names(ls: Labels) -> Text:
    out: list[Label] = []
    for k in sorted(ls):
        out.append(k + "=" + ls[k])
    return ",".join(out)


def trace(m: Ints) -> int:
    return sum(m[i][i] for i in range(len(m)))


t: Tree = [Leaf(1), Leaf(2), Leaf(3)]
print(early(t), total(t), t[0].same(Leaf(1)), first(t), twigs([Twig(4), Leaf(5)]))
print(names({"b": "β", "a": "α"}))
print(trace([[1, 2], [3, 4]]))
fm: Matrix[float] = [[0.5]]
print(fm)
