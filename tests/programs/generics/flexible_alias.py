# mypy_extensions' FlexibleAlias[T, X], as a type alias's value, stands for X with the alias's
# type argument in place of T, as mypy expands it: mypy's Bogus = FlexibleAlias[T, T] (here
# mods/flexalias.py) makes Bogus[list[int]] a list[int]. Also for a module's own alias, through
# the module's attribute (me.FlexibleAlias), an alias of the alias, a quoted annotation,
# Annotated, a type statement and a generic function's own T. CPython evaluates the unquoted
# annotations: its FlexibleAlias subscripts make objects, whose subscripts return T.
from typing import Annotated, TypeVar

import mypy_extensions as me
from mods.flexalias import Bogus
from mypy_extensions import FlexibleAlias

T = TypeVar("T")
U = TypeVar("U")
Pair = me.FlexibleAlias[U, tuple[U, U]]
Same = Bogus
type Rows[V] = FlexibleAlias[V, list[list[V]]]


class Node:
    def __init__(self, items: Bogus[list[int]], name: "Bogus[str]") -> None:
        self.items = items
        self.name = name

    def total(self) -> Bogus[int]:
        return sum(self.items)


def swap(p: Pair[str]) -> Pair[str]:
    return (p[1], p[0])


def scale(n: Annotated[Same[int], "count"], rows: Rows[float]) -> list[float]:
    return [x * n for row in rows for x in row]


def first(xs: Bogus[list[T]]) -> T:
    return xs[0]


node = Node([1, 2, 3], "n")
print(node.total(), node.name.upper(), swap(("a", "b")), scale(2, [[1.5], [2.0, 0.5]]))
print(first(["x", "y"]), first([4.5]) + 1)
