# Named union-valued constructor parameters bind their declared union, preserving
# members' Python types. Other concrete generic arguments still infer as before.
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, left: T, right: T = 0) -> None:
        self.left = left
        self.right = right
        self.values: list[T] = [left, right]

    def replace(self, value: T) -> None:
        self.right = value


def show(pair: Pair[int | float]) -> None:
    print(pair.values, pair.left, pair.right)
    print(isinstance(pair.left, int), isinstance(pair.right, float))


def make() -> Pair[int | float]:
    return Pair(5, 6.5)


show(Pair[int | float](1, 2.5))
show(Pair(1, 2.5))
show(Pair[int | float](9007199254740993, 2.5))
pair: Pair[int | float] = Pair(3, 4.5)
show(pair)
pair.replace(6.5)
print(pair.right)
show(Pair[int | float](1.5))
show(Pair[int | float](right=2.5, left=1))
show(Pair[int | float](*(1, 2.5)))
show(Pair[int | float](**{"left": 1, "right": 2.5}))
show(make())

nullable = Pair[int | str | None](None, "ok")
print(nullable.values, nullable.left is None, nullable.right)
print(Pair[bool | int](True, 1).values)
print(Pair[int | None](1, None).values)

# A union containing exact container types preserves the original mutable object.
ints = [1]
container = Pair[list[int] | dict[str, int]](ints, {"n": 2})
ints.append(3)
print(container.values)


def append(value: list[int] | dict[str, int]) -> None:
    if isinstance(value, list):
        value.append(4)


append(container.left)
print(ints)

# A narrower source union may flow to a larger named one without changing tags.
value: int | str = 7
wider = Pair[int | float | str](value, 2.5)
print(wider.values, isinstance(wider.left, int))


class Box(Generic[T]):
    def __init__(self, value: T = "default") -> None:
        self.value = value


# Consistent inferred bindings keep their concrete methods and representations,
# including arguments and defaults outside the named hint's members.
print(Box[int | float]("abc").value.upper())
print(Box[int | str]("ABC").value.lower())
print(Box[int | float]().value.upper())
print(Pair[int | str]("A", "B").left.lower())
inferred = Box[list[int | float] | dict[str, int]](ints)
inferred.value.append(5)
print(ints)
