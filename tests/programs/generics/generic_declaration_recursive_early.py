from typing import Generic, TypeVar

T = TypeVar("T")


class Cell(Generic[T]):
    other: "Cell[int] | None" = None

    def __init__(self, value: T) -> None:
        self.value = value


# Even an unused signature can request Cell[int] before its attributes are ready.
class Holder:
    def __init__(self, value: Cell[int]) -> None:
        self.value = value


first = Cell(1)
second = Cell[int](2)
print(first.value, first.other, second.value, second.other)
