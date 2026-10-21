from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def total(xs: Iterable[int]) -> int:
    return sum(xs)


def count() -> int:
    return 3
