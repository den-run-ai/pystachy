# A TypeVar's bound and constraints may name classes, also another module's (by import and as its
# attribute), type aliases and typing's forms, not only strings, as mypy's do
# (F = TypeVar("F", bound=FunctionLike), Targ = TypeVar("Targ", int, str, tuple[int, ...])).
# CPython evaluates them when the assignment runs, after what they name; Pystachy binds the
# variable by the arguments' types, as for a TypeVar without them.
from collections.abc import Callable
from typing import Any, TypeVar

import mods.shapes
from mods.shapes import Square


class Node:
    def name(self) -> str:
        return "node"


class Leaf(Node):
    def name(self) -> str:
        return "leaf"


Pair = tuple[int, int]
N = TypeVar("N", bound=Node)
F = TypeVar("F", bound=Callable[..., Any])
S = TypeVar("S", bound=Square | mods.shapes.Circle)
Targ = TypeVar("Targ", int, str, tuple[int, ...])
P = TypeVar("P", Pair, str, covariant=True)
L = TypeVar("L", bound="Leaf")


def first(xs: list[N]) -> N:
    return xs[0]


def inc(n: int) -> int:
    return n + 1


def same(f: F) -> F:
    return f


def side(s: S) -> S:
    return s


def show(x: Targ) -> Targ:
    print(type(x).__name__, x)
    return x


def swap(p: P) -> P:
    return p


def leaf(x: L) -> str:
    return x.name()


print(first([Node(), Leaf()]).name(), first([Leaf()]).name(), same(inc)(2), side(Square(3)).side)
print(show(3), show("s"), show((1, 2)), swap((1, 2)), swap("ab"), leaf(Leaf()))
