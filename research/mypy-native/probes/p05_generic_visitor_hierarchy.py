# mypy/types.py + mypy/type_visitor.py: Type.accept(visitor: TypeVisitor[T]) -> T with TypeVisitor(Generic[T]) subclasses
from abc import abstractmethod
from typing import Generic, TypeVar
T = TypeVar("T")
class TypeVisitor(Generic[T]):
    @abstractmethod
    def visit_instance(self, t: "Instance") -> T: ...
    @abstractmethod
    def visit_none(self, t: "NoneType") -> T: ...
class Type:
    def accept(self, visitor: TypeVisitor[T]) -> T:
        raise RuntimeError("not implemented")
class Instance(Type):
    def __init__(self, name: str) -> None:
        self.name = name
    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_instance(self)
class NoneType(Type):
    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_none(self)
class StrVisitor(TypeVisitor[str]):
    def visit_instance(self, t: Instance) -> str:
        return t.name
    def visit_none(self, t: NoneType) -> str:
        return "None"
class BoolQuery(TypeVisitor[bool]):
    def visit_instance(self, t: Instance) -> bool:
        return True
    def visit_none(self, t: NoneType) -> bool:
        return False
ts: list[Type] = [Instance("int"), NoneType()]
print([t.accept(StrVisitor()) for t in ts], [t.accept(BoolQuery()) for t in ts])
