# error: iter() returned non-iterator of type 'B'
from typing import Iterable

class A:
    def __iter__(self) -> 'B':
        return B()

class B:
    def __iter__(self) -> A:
        return A()

def items(xs: Iterable[int]) -> list[int]:
    return list(xs)

print(items(A()))
