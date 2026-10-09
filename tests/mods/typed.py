"""A module that uses typing's forms: collections.abc, Final and @overload (names qualified)."""
from collections.abc import Mapping, Sequence, Iterator
import collections.abc
import typing
from typing import Final, overload, MutableMapping

LIMIT: Final = 3
NAMES: Final[list[str]] = ["a", "b"]


@overload
def get(x: int) -> int: ...
@overload
def get(x: str) -> str: ...
def get(x: int) -> int:
    return x + LIMIT


@typing.overload
def total(xs: list[int]) -> int: ...
def total(xs: Sequence[int]) -> int:
    t: Final = 10
    n: Final[int] = len(xs)
    return sum(xs) + t * n


def keys(d: Mapping[str, int], e: collections.abc.MutableMapping[str, list[str]], f: MutableMapping[int, int]) -> list[str]:
    return sorted(d) + sorted(e) + [str(k) for k in f]


class Named:
    name: Final[str]

    def __init__(self, name: str) -> None:
        self.name = name

    @overload
    def twice(self, x: int) -> int: ...
    @overload
    def twice(self, x: str) -> str: ...
    def twice(self, x: int) -> int:
        return x * 2
