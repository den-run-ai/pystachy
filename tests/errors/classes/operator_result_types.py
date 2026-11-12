# error: operator dispatch methods must return one concrete type (optionally None)
from types import NotImplementedType


class Left:
    def __init__(self, accept: bool) -> None:
        self.accept = accept

    def __add__(self, other: object) -> int | NotImplementedType:
        if self.accept:
            return 1
        return NotImplemented


class Right:
    def __radd__(self, other: object) -> str:
        return "different storage"


print(Left(False) + Right())
