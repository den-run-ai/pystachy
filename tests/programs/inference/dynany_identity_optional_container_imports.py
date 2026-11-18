# pystachy: dynamic-any
from typing import Any
from typed_storage import first, frozen, make, replace


def same(a: Any, b: Any) -> bool:
    return a is b


original: Any = float("nan")
other: Any = float("nan")
values = make(original)
items = frozen(values)
print("returned", same(values[0], original), same(values[-1], original), values[1] is None)
print("snapshot", same(first(items), original), items[1] is None, same(items[-1], original))
print("replace", same(replace(values, other), original), same(values[0], other), same(first(items), original))
print("none", replace(values, None) is other, values[0] is None)
