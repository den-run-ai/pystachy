from typing import Generic, TypeVar

T = TypeVar("T")


class Inner(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def __repr__(self) -> str:
        return repr(self.value)


class Outer(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def __repr__(self) -> str:
        return repr(Inner(self.value))


def show(box: Outer[int]) -> None:
    print(box)


show(Outer(7))
print(Outer("yes"))
