# Existing generic call inference wins over annotations that used to be erased.
from typing import Callable, Generic, Iterable, TypeVar

T = TypeVar("T")


class Callback(Generic[T]):
    def __init__(self, read: Callable[[], T]) -> None:
        self.read: Callable[[], T] = read


def choose(left: T, right: T) -> T:
    return right


def result(value: T) -> T:
    return "inferred result"


def explicit_context(value: T) -> Callback[str]:
    def read() -> T:
        return "existing callable context"
    return Callback[str](read)


class UnusedIterable:
    def __init__(self, value: int) -> None:
        self.value = value

    def __iter__(self):
        # This method must not be compiled just to resolve an ignored annotation.
        return unsupported_name


def ignored(source: Iterable[T]) -> int:
    return 17


assert choose(1, "right") == "right"
assert result(1) == "inferred result"
assert explicit_context(1).read() == "existing callable context"
assert ignored(UnusedIterable(1)) == 17
print("legacy inference and unused generic annotations preserved")
