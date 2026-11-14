from collections import defaultdict
from typing import Generic, Iterable, Iterator, TypeVar

T = TypeVar("T")


class Errors:
    def __init__(self) -> None:
        self.items: defaultdict[str, set[str]] = defaultdict(set)


class Root:
    def __init__(self, values: Iterable[int]) -> None:
        self.count: int = sum(values)


class Producer(Root):
    def __init__(self, errors: Errors) -> None:
        self.errors: Errors = errors
        self.count: int = len(errors.items)

    def repeat(self, value: float) -> Iterator[float]:
        for _ in range(self.count):
            yield value


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def get(self) -> T:
        return self.value


def is_box(value):
    return type(value) is Box and Box is type(value) and isinstance(value, Box)


def widen(values: tuple[float, ...]) -> tuple[float | None, ...]:
    return values
