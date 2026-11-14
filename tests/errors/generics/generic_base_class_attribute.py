# error: generic_base_class_attribute.py:10: error: a class attribute of a generic class in a hierarchy is not supported: assign it in __init__ (Fut.limit)
# A generic class's specializations share its class attributes, which the classes of a
# hierarchy would each need their own of (generic_bases.py assigns fields in __init__).
from typing import Generic, TypeVar
T = TypeVar("T")
class Base:
    def __init__(self) -> None:
        self.n = 0
class Fut(Base, Generic[T]):
    limit = 3
    def __init__(self, v: T) -> None:
        super().__init__()
        self.v = v
print(Fut(1).v)
