# error: cannot bind its type variables from the argument for 'read'
from typing import Callable, Generic, Self, TypeVar

T = TypeVar("T")


class Callback(Generic[T]):
    def __init__(self, read: Callable[[], T]) -> None:
        self.read: Callable[[], T] = read


def unrelated(value: T):
    def read() -> tuple[Self, T]:
        return value, value
    return Callback(read)


print(unrelated(1).read())
