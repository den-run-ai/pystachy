# generic class as a base, without the virtual generic method (mypy/type_visitor.py: TypeTranslator(TypeVisitor[Type]))
from typing import Generic, TypeVar
T = TypeVar("T")
class Query(Generic[T]):
    def __init__(self, default: T) -> None:
        self.default = default
    def result(self) -> T:
        return self.default
class BoolQuery(Query[bool]):
    def __init__(self) -> None:
        super().__init__(False)
    def result(self) -> bool:
        return not self.default
print(BoolQuery().result(), Query(3).result())
