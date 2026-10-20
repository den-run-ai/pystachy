# Conflicting direct scalar TypeVars fall back to a closed union, after ordinary
# inference. Arguments still evaluate once in Python order and retain their types.
from typing import Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")


class Pair(Generic[T]):
    def __init__(self, left: T, right: T = 0) -> None:
        self.left = left
        self.right = right
        self.values: list[T] = [left, right]

    def replace(self, value: T) -> None:
        self.right = value


numbers = Pair(9007199254740993, 2.5)
print(numbers.values, isinstance(numbers.left, int), isinstance(numbers.right, float))
numbers.replace(3)
print(numbers.right)
print(Pair(1, "x").values)
print(Pair(None, "text").values)
print(Pair(1, None).values)
print(Pair(2.5).values)
print(Pair(right="s", left=2).values)
print(Pair(*(3, "star")).values)
print(Pair(**{"left": 4, "right": "kw"}).values)

# Wider source unions retain every member and the optional tag.
value: int | str = "value"
print(Pair(value, 1.5).values)
optional: int | None = None
print(Pair(optional, "present").values)


class Triple(Generic[T, U]):
    def __init__(self, a: "T", b: T, c: T, other: U) -> None:
        self.values: list[T] = [a, b, c]
        self.other = other


triple = Triple(True, 1, "flag", [2])
print(triple.values, triple.other)
print(isinstance(triple.values[0], bool), isinstance(triple.values[1], int))
triple.other.append(3)
print(triple.other)


# Arguments are not re-evaluated during the fallback.
def integer() -> int:
    print("integer")
    return 1


def text() -> str:
    print("text")
    return "two"


print(Pair(right=text(), left=integer()).values)

# Existing consistent inference keeps concrete operations and ignores named
# hints outside the inferred type. Containers do not acquire inferred unions.
print(Pair("A", "B").left.lower())
print(Pair[int | float]("A", "B").right.lower())
same = Pair([1], [2])
same.left.append(3)
print(same.values)
print(Pair(True, False).left)
print(Pair(True, 1).values)
