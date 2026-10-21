# error: Stack() does not bind its type variable 'T': no argument's type gives it
# A function's C() takes no type from its caller (a lambda's from its Callable): -> Stack[int]
from typing import Generic, TypeVar

T = TypeVar("T")


class Stack(Generic[T]):
    def __init__(self) -> None:
        self.items: list[T] = []


def make():
    return Stack()


s: Stack[int] = make()
print(s.items)
