# error: Pair() cannot bind its type variables from the argument for 'a', a list[int]: it does not fit the parameter's annotation
# Box[T] in __init__'s annotation matches an object of a specialization of Box, not a list
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, x: T) -> None:
        self.x = x


class Pair(Generic[T]):
    def __init__(self, a: Box[T], b: "Box[T] | list[T]") -> None:
        self.a = a
        self.b = b


p = Pair([1], Box(2))
print(p.a)
