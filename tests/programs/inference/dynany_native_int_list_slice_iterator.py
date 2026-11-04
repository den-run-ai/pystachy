# pystachy: dynamic-any
# With no source-level try or __next__, nested slice stores still replace an
# initial iterator failure. Ordinary static slices need no exception region.
from typing import Any


class InvalidIterator:
    def __iter__(self) -> int:
        print("acquire")
        return 1


native: list[int] = [7]
target: Any = native
value: Any = InvalidIterator()
target[:], tag = (value, 42)
