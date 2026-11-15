# error: expected int, got str
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Callback(Generic[T]):
    def __init__(self, read: Callable[[], T]) -> None:
        self.read: Callable[[], T] = read


def wrong(value: T):
    def read() -> T:
        return "wrong"
    return Callback(read)


print(wrong(1).read())
