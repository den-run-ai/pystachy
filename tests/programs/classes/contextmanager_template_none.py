from contextlib import contextmanager
from typing import Generic, Iterator, TypeVar

T = TypeVar("T")


class Scope(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    @contextmanager
    def opened(self, x: int) -> Iterator[int]:
        print("template enter", self is None)
        yield x
        print("template exit")

    @contextmanager
    def read(self) -> Iterator[T]:
        print("template read enter")
        yield self.value


def check(present: bool) -> None:
    scope = Scope(17)
    if not present:
        scope = None
    try:
        manager = Scope.opened(scope, 3)
        print("template created")
        with manager as value:
            print("template value", value)
    except AttributeError as error:
        print("unexpected", str(error))
    try:
        reader = Scope.read(scope)
        print("template reader created")
        with reader as value:
            print("template read", value)
    except AttributeError as error:
        print("template error", str(error))


check(False)
check(True)
