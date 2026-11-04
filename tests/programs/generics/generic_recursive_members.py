from typing import Generic, TypeVar

T = TypeVar("T")


class Left(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value
        self.right: Right[T] | None = None


class Right(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value
        self.left: Left[T] | None = None


# Construction precedes the annotation; the cycle has one layout for each class.
first = Left(4)
Alias = Left
second: Alias[int] = first
second.right = Right(8)
second.right.left = first
print(first.value, first.right.value, first.right.left is first)
text: Left[str] = Left("left")
text.right = Right("right")
print(text.value, text.right.value)
