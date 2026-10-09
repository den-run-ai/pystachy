# A module global that more than one T = TypeVar("T") binds is a TypeVar: the def statements
# evaluate list[T] and T | None (also an imported module's, used or not), and the functions
# whose parameters mention it are templates
from typing import TypeVar

from mods.tvtwice import size

T = TypeVar("T")


def f(x: list[T]) -> int:
    return len(x)


T = TypeVar("T")


def g(x: T | None) -> bool:
    return x is None


print(f([1, 2]), g(None), g(3), g("a"))
print(size([1, 2, 3]), size(["a"]))
