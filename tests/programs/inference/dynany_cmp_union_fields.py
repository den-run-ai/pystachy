# pystachy: dynamic-any
from typing import Any


class Fixed:
    def __init__(self) -> None:
        self.force = [1]
        self.items = (1, 2)


class Variable:
    def __init__(self) -> None:
        self.force = [1]
        self.items: tuple[float, ...] = (1.0, 2.0)

    def __eq__(self, other: "Variable") -> bool:
        print("variadic ran")
        return self.force == other.force and self.items == other.items


class Union:
    def __init__(self, scalar: bool) -> None:
        self.force = [1]
        self.items: int | list[int] = 1 if scalar else [1, 2]

    def __eq__(self, other: "Union") -> bool:
        print("union ran")
        return self.force == other.force and self.items == other.items


class Text:
    def __init__(self) -> None:
        self.force = [1]
        self.items: tuple[str, ...] = ("one", "two")


x: Any = Variable()
y: Any = Fixed()
print(x == y, y == x, x != y, y in [x])
y = Text()
print(x == y, y == x, x != y)
for scalar in [False, True]:
    x = Union(scalar)
    y = Fixed()
    print(x == y, y == x, x != y)
    y = Text()
    print(x == y, y == x)
    print(Union(scalar) == Union(scalar))
