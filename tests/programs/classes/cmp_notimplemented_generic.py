# A generic class's __eq__ that returns NotImplemented.
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v

    def __eq__(self, other):
        if not isinstance(other, Box):
            return NotImplemented
        return self.v == other.v


xs = [Box(1), Box(1), Box(2)]
ys = [Box("a"), Box("a"), Box("b")]
print(xs[0] == xs[1], xs[0] == xs[2], xs[0] == 3, xs[0] != xs[1], xs[0] != xs[2])
print(ys[0] == ys[1], ys[0] == ys[2], ys[0] != "a", ys[0] == None)
