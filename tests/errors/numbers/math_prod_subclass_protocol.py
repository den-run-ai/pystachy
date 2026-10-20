# error: math.prod() with subclass-dependent multiplication protocols requires narrowing with isinstance() first
from math import prod


class Index:
    def __index__(self) -> int:
        return 2


class Reflected(Index):
    def __rmul__(self, value: str) -> str:
        return "reflected"


values: list[Index] = [Reflected()]
print(prod(values, start="a"))
