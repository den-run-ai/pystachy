# error: Tagged[...] needs each parameter of Tagged.__init__ annotated, and no *args or **kwargs: 'tag' is not
from typing import Generic, TypeVar

T = TypeVar("T")


class Tagged(Generic[T]):
    def __init__(self, value: T, tag) -> None:
        self.value = value
        self.tag = tag


t: Tagged[int] = Tagged(1, "t")
print(t.value)
