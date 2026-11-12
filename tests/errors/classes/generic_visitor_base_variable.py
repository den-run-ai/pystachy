# error: overrides of RTypeVisitor.visit_rprimitive() return incompatible types
# A visitor held where its base is declared (v: RTypeVisitor[str]) is an RTypeVisitor, whose
# methods dispatch to every visitor class: those of two families return str and bool. Pass the
# visitor object itself, or a variable of its own class
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


types: list[RType] = [RPrimitive("int"), RTuple([RPrimitive("int"), RPrimitive("str")]), RPrimitive("str")]
for x in types:
    print(x.accept(TupleNameVisitor()), x.accept(IsTupleVisitor()))
print(isinstance(TupleNameVisitor(), RTypeVisitor))
v: RTypeVisitor[str] = TupleNameVisitor()
print(RPrimitive("int").accept(v))
