# Visitors (#962): classes deriving from a generic class without an __init__ of its own, which
# binds nothing (RTypeVisitor[str] is RTypeVisitor), and accept(self, visitor: RTypeVisitor[T]) -> T,
# whose T the visitor's class binds (str, bool) before the body compiles, so that a visitor's
# recursive accept() knows it; each object's accept() dispatches on its class; subclasses that
# inherit accept() take it too
from typing import Generic, TypeVar

T = TypeVar("T")


class RTypeVisitor(Generic[T]):
    def visit_rprimitive(self, t: "RPrimitive") -> T:
        raise NotImplementedError

    def visit_rtuple(self, t: "RTuple") -> T:
        raise NotImplementedError


class RType:
    def accept(self, visitor: "RTypeVisitor[T]") -> T:
        raise NotImplementedError


class RPrimitive(RType):
    def __init__(self, name: str) -> None:
        self.name = name

    def accept(self, visitor: "RTypeVisitor[T]") -> T:
        return visitor.visit_rprimitive(self)


class RTuple(RType):
    def __init__(self, types: list[RType]) -> None:
        self.types = types

    def accept(self, visitor: "RTypeVisitor[T]") -> T:
        return visitor.visit_rtuple(self)


class RNamed(RPrimitive):
    pass


class RNested(RTuple):
    def label(self) -> str:
        return "nested"


class TupleNameVisitor(RTypeVisitor[str]):
    def visit_rprimitive(self, t: RPrimitive) -> str:
        return "I" if t.name == "int" else "O"

    def visit_rtuple(self, t: RTuple) -> str:
        return "T" + "".join([x.accept(self) for x in t.types])


class IsTupleVisitor(RTypeVisitor[bool]):
    def visit_rprimitive(self, t: RPrimitive) -> bool:
        return False

    def visit_rtuple(self, t: RTuple) -> bool:
        return True


types: list[RType] = [RPrimitive("int"), RTuple([RPrimitive("int"), RPrimitive("str")]), RNamed("str"), RNested([RNamed("int"), RNested([RPrimitive("x")])])]
for x in types:
    print(x.accept(TupleNameVisitor()), x.accept(IsTupleVisitor()))
print(isinstance(TupleNameVisitor(), RTypeVisitor))
