# Caller annotations require the named generic storage even for homogeneous
# arguments. Explicit constructor subscriptions alone remain inference hints.
from typing import Generic, TypeVar

T = TypeVar("T")


class Pair(Generic[T]):
    def __init__(self, left: T, right: T = 0) -> None:
        self.left = left
        self.right = right
        self.values: list[T] = [left, right]

    def replace(self, value: T) -> None:
        self.right = value


class Box(Generic[T]):
    def __init__(self, value: T = "default") -> None:
        self.value = value


def show(pair: Pair[int | float]) -> None:
    print(pair.values, isinstance(pair.left, int), isinstance(pair.right, int))
    pair.replace(2.5)
    print(pair.right)


def make() -> Pair[int | float]:
    return Pair(3, 4)


pair: Pair[int | float] = Pair(9007199254740993, 2)
show(pair)
show(Pair(5, 6))
show(Pair(7))
show(Pair[int | float](8, 9))
show(Pair[int | str](*(10, 11)))
show(Pair(**{"left": 12, "right": 13}))
show(make())
optional_pair: Pair[int | float] | None = Pair(16, 17)
if optional_pair is not None:
    show(optional_pair)
flags: Pair[bool | int] = Pair(True, False)
print(flags.values, isinstance(flags.left, bool))
flags.replace(1)
print(flags.right)


class Holder:
    def __init__(self) -> None:
        self.pair: Pair[int | float] = Pair(14, 15)


show(Holder().pair)
maybe: Pair[int | None] = Pair(1, 2)
maybe.replace(None)
print(maybe.values, maybe.right)
nullable: Box[int | str | None] = Box(None)
print(nullable.value is None)
box: Box[int | str] = Box()
print(box.value)

# A narrower union widens by remapping tags, retaining the original scalar value.
value: int | str = "text"
wider: Pair[int | str | float] = Pair(value, value)
print(wider.values, isinstance(wider.left, str))

# A union member can hold an existing container when its type fits exactly.
ints = [1]
containers: Box[list[int] | dict[str, int]] = Box(ints)


def extend(value: list[int] | dict[str, int]) -> None:
    if isinstance(value, list):
        value.append(2)


extend(containers.value)
print(ints)


def left() -> int:
    print("left")
    return 1


def right() -> int:
    print("right")
    return 2


ordered: Pair[int | float] = Pair(right=right(), left=left())
print(ordered.values)
starred: Pair[int | float] = Pair[int | float](*(left(), right()))
print(starred.values)

# Standalone hints and calls without a destination retain concrete operations.
print(Box[int | str]("ABC").value.lower())
print(Box[int | str](*("DEF",)).value.lower())
print(Box[int | float]().value.upper())
print(Pair[int | float]("A", "B").left.lower())
print(Pair("C", "D").right.lower())
