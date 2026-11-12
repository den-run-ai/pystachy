from typing import Final, Generic, TypeVar
T = TypeVar("T")
class Box(Generic[T]):
    KINDS: Final = ["a", "b"]
    N: Final = 2
    def __init__(self, v: T) -> None:
        self.v: Final = v
b = Box(3)
print(Box.KINDS, b.N, b.v, Box("s").v)
