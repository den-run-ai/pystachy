from typing import Generic, Iterable, Self, TypeVar

T = TypeVar("T")


def seed() -> list[int]:
    print("default")
    return [3]


class Box(Generic[T]):
    def __init__(self, items: Iterable[T] = seed()) -> None:
        self.items: list[T] = list(items)

    def __repr__(self) -> str:
        return repr(self.items)

    def __neg__(self) -> Self:
        out: Box[T] = Box()
        return out


def show(box: Box[int]) -> None:
    print(box)


show(Box())
show(-Box([4]))
show(Box())
