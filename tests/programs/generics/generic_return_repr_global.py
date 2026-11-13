from typing import Generic, TypeVar

T = TypeVar("T")
READY = "ready"


class Box(Generic[T]):
    def __init__(self, item: T) -> None:
        self.item = item

    def __repr__(self) -> str:
        return READY


def make() -> Box[int]:
    return Box(1)


print(make())
READY = "changed"
print(make())
