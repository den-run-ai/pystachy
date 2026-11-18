from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def get(self) -> T:
        return self.value


def typed_box(value):
    box = Box(value)
    print(isinstance(box, Box))
    return box


def is_box(value):
    return isinstance(value, Box)
