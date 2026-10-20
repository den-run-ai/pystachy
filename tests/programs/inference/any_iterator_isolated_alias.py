from typing import Any as Item
from collections.abc import Iterable


class Values:
    def __iter__(self) -> "Iterable[Item]":
        return iter(["red", "green"])


print(list(Values()))
