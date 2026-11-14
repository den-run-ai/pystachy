# mypy's visitors (#962): NodeVisitor(Generic[T], ExpressionVisitor[T], StatementVisitor[T]) has
# two generic method-only bases, which pass its T on; nodes' accept() takes one of them, and the
# visitor's class binds T through NodeVisitor (Printer: str, Summer: None). An abstract method a
# base declares and nothing overrides runs its own body; isinstance() sees every base
from __future__ import annotations

from abc import abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class ExpressionVisitor(Generic[T]):
    @abstractmethod
    def visit_int(self, o: IntExpr, /) -> T:
        pass

    @abstractmethod
    def visit_name(self, o: NameExpr, /) -> T:
        pass


class StatementVisitor(Generic[T]):
    @abstractmethod
    def visit_pass(self, o: PassStmt, /) -> T:
        pass

    def visit_extra(self, o: PassStmt, /) -> T | None:
        return None


class NodeVisitor(Generic[T], ExpressionVisitor[T], StatementVisitor[T]):
    def visit_int(self, o: IntExpr, /) -> T:
        raise NotImplementedError()

    def visit_name(self, o: NameExpr, /) -> T:
        raise NotImplementedError()

    def visit_pass(self, o: PassStmt, /) -> T:
        raise NotImplementedError()


class Node:
    def accept(self, visitor: NodeVisitor[T]) -> T:
        raise NotImplementedError()


class IntExpr(Node):
    def __init__(self, v: int) -> None:
        self.v = v

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_int(self)


class NameExpr(Node):
    def __init__(self, name: str) -> None:
        self.name = name

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_name(self)


class PassStmt(Node):
    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_pass(self)


class Printer(NodeVisitor[str]):
    def visit_int(self, o: IntExpr, /) -> str:
        return "int " + str(o.v)

    def visit_name(self, o: NameExpr, /) -> str:
        return "name " + o.name

    def visit_pass(self, o: PassStmt, /) -> str:
        return "pass"


class LoudPrinter(Printer):
    def visit_name(self, o: NameExpr, /) -> str:
        return super().visit_name(o).upper()


class Summer(NodeVisitor[None]):
    def __init__(self) -> None:
        self.total = 0

    def visit_int(self, o: IntExpr, /) -> None:
        self.total += o.v


def show(nodes: list[Node], v: Printer) -> list[str]:
    return [n.accept(v) for n in nodes]


nodes: list[Node] = [IntExpr(3), NameExpr("x"), PassStmt(), IntExpr(4)]
print(show(nodes, Printer()))
print(show(nodes, LoudPrinter()))
s = Summer()
for n in nodes:
    if isinstance(n, IntExpr):
        n.accept(s)
print(s.total)
try:
    PassStmt().accept(s)
except NotImplementedError:
    print("Summer has no visit_pass")
print(Printer().visit_extra(PassStmt()), s.visit_extra(PassStmt()))
print(isinstance(s, ExpressionVisitor), isinstance(s, StatementVisitor), isinstance(Printer(), NodeVisitor))
