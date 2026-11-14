# Visitors under postponed annotations, as mypyc's rtypes.py writes them: forward references,
# a visitor deriving from another, one that returns None and has an __init__ of its own, a generic
# class of two TypeVars, a base named without its type arguments, a field stored from
# self.accept(Visitor()), a method of the generic class itself, and NotImplementedError where a
# visitor has no method of its own
from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class RType:
    def accept(self, visitor: RTypeVisitor[T]) -> T:
        raise NotImplementedError

    def describe(self) -> str:
        return self.accept(TupleNameVisitor())


class RPrimitive(RType):
    def __init__(self, name: str) -> None:
        self.name = name

    def accept(self, visitor: RTypeVisitor[T]) -> T:
        return visitor.visit_rprimitive(self)


class RTuple(RType):
    def __init__(self, types: list[RType]) -> None:
        self.types = types
        self.unique_id = self.accept(TupleNameVisitor())

    def accept(self, visitor: RTypeVisitor[T]) -> T:
        return visitor.visit_rtuple(self)


class RTypeVisitor(Generic[T]):
    def visit_rprimitive(self, t: RPrimitive, /) -> T:
        raise NotImplementedError

    def visit_rtuple(self, t: RTuple, /) -> T:
        raise NotImplementedError

    def kind(self) -> str:
        return "visitor"


class TupleNameVisitor(RTypeVisitor[str]):
    def visit_rprimitive(self, t: RPrimitive) -> str:
        return "I" if t.name == "int" else "O"

    def visit_rtuple(self, t: RTuple) -> str:
        return "T" + str(len(t.types)) + "".join([x.accept(self) for x in t.types])


class LoudNames(TupleNameVisitor):
    def visit_rprimitive(self, t: RPrimitive) -> str:
        return t.name.upper()


class Counter(RTypeVisitor[None]):
    def __init__(self) -> None:
        self.count = 0

    def visit_rprimitive(self, t: RPrimitive) -> None:
        self.count += 1

    def visit_rtuple(self, t: RTuple) -> None:
        self.count += 1
        for x in t.types:
            x.accept(self)


class Pair(Generic[K, V]):
    def first(self, k: K) -> K:
        return k


class IntStr(Pair[int, str]):
    def second(self) -> str:
        return "s"


class Plain(RTypeVisitor):
    def visit_rprimitive(self, t: RPrimitive) -> int:
        return len(t.name)


nested = RTuple([RPrimitive("int"), RTuple([RPrimitive("str")]), RPrimitive("bool")])
print(nested.unique_id, nested.describe(), nested.accept(LoudNames()))
c = Counter()
nested.accept(c)
print(c.count, TupleNameVisitor().kind(), isinstance(LoudNames(), RTypeVisitor))
print(IntStr().first(3), IntStr().second(), RPrimitive("float").accept(Plain()))
try:
    nested.accept(Plain())
except NotImplementedError:
    print("NotImplementedError")
