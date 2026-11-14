# A generic class whose generic base passes its type variable on (Mid(Generic[S], NodeVisitor[S]),
# NodeVisitor(Generic[T], ExprVisitor[T], StmtVisitor[T], Named)) binds it for accept() through
# each step (Describer(Mid[str]): str, Counter(Mid[int]): int); Named is a plain secondary base
from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")
S = TypeVar("S")


class ExprVisitor(Generic[T]):
    def visit_num(self, o: Num, /) -> T:
        raise NotImplementedError()


class StmtVisitor(Generic[T]):
    def visit_stop(self, o: Stop, /) -> T:
        raise NotImplementedError()


class Named:
    def label(self) -> str:
        return "visitor"


class NodeVisitor(Generic[T], ExprVisitor[T], StmtVisitor[T], Named):
    pass


class Mid(Generic[S], NodeVisitor[S]):
    def visit_stop(self, o: Stop, /) -> S:
        return self.default()

    def default(self) -> S:
        raise NotImplementedError()


class Num:
    def __init__(self, v: int) -> None:
        self.v = v

    def accept(self, visitor: ExprVisitor[T]) -> T:
        return visitor.visit_num(self)


class Stop:
    def accept(self, visitor: StmtVisitor[T]) -> T:
        return visitor.visit_stop(self)


class Describer(Mid[str]):
    def visit_num(self, o: Num, /) -> str:
        return "num " + str(o.v)

    def default(self) -> str:
        return "stop"

    def label(self) -> str:
        return "describer"


class Counter(Mid[int]):
    def visit_num(self, o: Num, /) -> int:
        return o.v + 1

    def default(self) -> int:
        return -1


d = Describer()
c = Counter()
print(Num(5).accept(d) + "!", Num(5).accept(c) * 10, Stop().accept(d).upper(), Stop().accept(c) - 1)
named: list[Named] = [d, c, Named()]
print([n.label() for n in named], isinstance(c, Named), isinstance(c, StmtVisitor), isinstance(Named(), ExprVisitor))
