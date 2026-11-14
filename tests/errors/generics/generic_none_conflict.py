# error: Pair() cannot bind its type variables from the argument for 'a', a None: 'T' would be None, which Pystachy binds no type variable to (a list or dict of None values has no type)
# None binds a type variable only where no other argument does (generic_none_binding.py): here
# the list binds T, and a list[int] cannot be None.
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, a: T, b: T) -> None:
        self.a = a
        self.b = b


print(Pair(None, [1]).b)
