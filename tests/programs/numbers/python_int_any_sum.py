# pystachy: dynamic-any
# pystachy: python-int
# Overflow ends CPython's small-int sum phase; wide operands also end its
# compensated float phase. Subsequent additions stay generic.
from typing import Any


def check(xs: list[Any]) -> None:
    obj: Any = xs
    print(sum(xs), sum(obj), sum(x for x in xs))


wide: Any = 2 ** 70
check([wide, -wide, 1e16, 1.0, -1e16])
check([9223372036854775807, 1, -9223372036854775808, 1e16, 1.0, -1e16])
check([1e16, 1.0, -1e16, wide, -wide, 1e16, 1.0, -1e16])
check([1e16, 1.0, -1e16, wide])
empty: list[Any] = []
print("empty wide identity", sum(empty, wide) is wide)
start: int = 2 ** 70
obj: Any = empty
print("wide start", sum(empty, start), sum(obj, start), sum((x for x in empty), start))


class ObserveWideStart:
    def __radd__(self, other: Any) -> Any:
        print("wide callback identity", other is wide)
        return 1.0


items: list[Any] = [ObserveWideStart()]
boxed_items: Any = items
print("wide callback", sum(items, wide), sum(boxed_items, wide), sum((x for x in items), wide))
