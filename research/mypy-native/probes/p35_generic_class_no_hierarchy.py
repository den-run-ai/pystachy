from typing import Generic, TypeVar
T = TypeVar("T")
class Box(Generic[T]):
    def __init__(self, v: T) -> None:
        self.v = v
    def get(self) -> T:
        return self.v
print(Box(1).get(), Box("s").get())
