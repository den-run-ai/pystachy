# error: generic_base_exception.py:5: error: a generic class's base must be an ordinary class of the program declared before it, or a generic class's G[T] of its type variables: ValueError is not
# A generic exception class is not supported.
from typing import Generic, TypeVar
T = TypeVar("T")
class Fut(ValueError, Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v
print(Fut(1).v)
