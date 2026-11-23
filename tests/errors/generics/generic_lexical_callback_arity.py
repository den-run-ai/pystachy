# error: it has 1 item where the annotation has 0
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Callback(Generic[T]):
    def __init__(self, read: Callable[[], T]) -> None:
        self.read: Callable[[], T] = read


def wrong(value: T):
    def read(extra: T) -> T:
        return extra
    return Callback(read)


print(wrong(1).read())
