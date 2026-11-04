# pystachy: dynamic-any
# Equality can replace the current items before list ordering compares them.
# A native/boxed pair must reload both slots instead of ordering stale values.
from typing import Any


class ReplacingQuery:
    def __init__(self, native: list[int], boxed: list[Any]) -> None:
        self.native = native
        self.boxed = boxed

    def __eq__(self, other: Any) -> bool:
        print("equality", other)
        self.native[0] = 9
        self.boxed[0] = 0
        return False

    def __gt__(self, other: Any) -> bool:
        print("stale ordering", other)
        return True


native: list[int] = [1]
boxed: list[Any] = [None]
boxed[0] = ReplacingQuery(native, boxed)
left: Any = native
right: Any = boxed
print("reloaded ordering", left < right, native, boxed)
