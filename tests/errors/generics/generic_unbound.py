# error: Stack() does not bind its type variable 'T': no argument's type gives it; name it where the object goes (q: Stack[int] = Stack(...), a field or a parameter annotated so) or in the call (Stack[int](...))
from typing import Generic, TypeVar

T = TypeVar("T")


class Stack(Generic[T]):
    def __init__(self, top: T | None) -> None:
        self.items: list[T] = []
        if top is not None:
            self.items.append(top)


print(Stack(None).items)
