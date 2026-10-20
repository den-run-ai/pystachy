# Only value-producing parts receive a generic constructor's contextual type.
# Typed call arguments, comprehension iterables and filters type themselves.
from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value


def numbers(xs: list[int]) -> list[int]:
    return [1, 2]


def count(xs: list[int]) -> int:
    return 3


def one() -> int:
    return 1


def ints(xs: list[int]) -> list[int]:
    return xs


def groups(xs: list[list[int]]) -> list[list[int]]:
    return xs


def pairs(xs: tuple[list[int], list[int]]) -> tuple[list[int], list[int]]:
    return xs


def mapping(xs: dict[str, int]) -> dict[str, int]:
    return xs


def optional(xs: list[int | None]) -> list[int | None]:
    return xs


def flags(xs: list[bool]) -> list[bool]:
    return xs


print(ints(Box[list[float]]([x for x in numbers([])]).value))
print(groups(Box[list[list[float]]]([[x] for x in numbers([])]).value))
print(pairs(Box[tuple[list[float], list[int]]](([1], numbers([]))).value))
print(ints(Box[list[float]]([count([])]).value))
print(ints(Box[list[float]]([1 if count([]) else 2]).value))
print(ints(Box[list[float]]([count([]) + 1]).value))
print(mapping(Box[dict[str, float]]({"a": count([])}).value))
print(Box[dict[str, int]]({count([]): 1}).value)
print(Box[set[str]]({count([])}).value)
print(ints(Box[list[float]]([x for x in [1, 2] if count([])]).value))

# Unknown expression types are not evidence of heterogeneous values; known
# types use the compiler's ordinary join (including None and repeated bools).
print(ints(Box[list[float | str]]([one(), 1]).value))
print(ints(Box[list[int | str]]([one(), 1]).value))
print(ints(Box[list[int | str]]([1 + 1, 2]).value))
print(mapping(Box[dict[str, float | str]]({"a": one(), "b": 1}).value))
print(optional(Box[list[int | str | None]]([None, 1]).value))
print(optional(Box[list[int | str | None]]([1, None]).value))
print(flags(Box[list[int | str]]([True, False]).value))
print(Box[list[bool | int]]([True, 1]).value)
print(Box[list[int | str]]([1, "mixed"]).value)

# The result body and independent tuple fields still receive empty hints;
# conditions and later values inherit what the first value already inferred.
print(groups(Box[list[list[int]]]([[] for x in [1, 2]]).value))
print(pairs(Box[tuple[list[int], list[int]]](([], [])).value))
print(ints(Box[list[int]]([] if count([]) else [1]).value))
print(ints(Box[list[float]]([1] if count([]) else []).value))
print(ints(Box[list[int]]([] or [1]).value))
