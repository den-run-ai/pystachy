# typing.final, and mypy_extensions' trait and mypyc_attr(...) of constant arguments, are class
# decorators that CPython applies as the identity (mypy's classes use them): classes keep their
# inheritance, virtual calls and isinstance(), also under @final above @dataclass and on an
# exception class. mypy_extensions' native integer names are int, as CPython's convert to int.
import typing
from dataclasses import dataclass
from typing import final

from mypy_extensions import i64, mypyc_attr, trait, u8


@trait
class Node:
    def kind(self) -> str:
        return "node"


@mypyc_attr(allow_interpreted_subclasses=True)
class Expr(Node):
    def kind(self) -> str:
        return "expr"


@final
@mypyc_attr("serializable", native_class=False)
class IntExpr(Expr):
    def __init__(self, value: i64) -> None:
        self.value = value

    def kind(self) -> str:
        return "int"


@typing.final
class StrExpr(Expr):
    pass


@final
@dataclass(frozen=True)
class Pos:
    line: int
    column: u8


@final
class CheckError(Exception):
    pass


def total(xs: list[i64]) -> i64:
    t: i64 = 0
    for x in xs:
        t += i64(x)
    return t


nodes: list[Node] = [Node(), Expr(), IntExpr(7), StrExpr()]
print([n.kind() for n in nodes], [isinstance(n, Expr) for n in nodes])
print(IntExpr(i64("12")).value, Pos(3, u8(200)), total([1, 2, 3]), u8(300), i64(2.9), isinstance(5, i64))
try:
    raise CheckError("bad")
except CheckError as e:
    print(type(e).__name__, e)
