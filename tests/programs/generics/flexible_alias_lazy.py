# A FlexibleAlias type alias that another module binds, in annotations that CPython never
# evaluates (as mypy/types.py's): Bogus[X] | None is X | None, and Bogus[X] holds X's methods.
from __future__ import annotations

from mods.flexalias import Bogus


class Box:
    def __init__(self, values: Bogus[list[str]], limit: Bogus[int] | None) -> None:
        self.values = values
        self.limit = limit

    def copy_modified(self, values: Bogus[list[str]] | None = None) -> Box:
        return Box(self.values if values is None else values, self.limit)


b = Box(["a"], None).copy_modified(["b", "c"])
print(b.values, b.limit, ",".join(b.values).upper())
