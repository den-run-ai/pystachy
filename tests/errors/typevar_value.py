# error: TypeVar 'T' cannot be used as a value (only annotations may name it)
from typing import TypeVar

T = TypeVar("T")
print(T)
