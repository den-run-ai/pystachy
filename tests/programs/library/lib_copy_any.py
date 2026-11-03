# pystachy: dynamic-any
# copy.copy() and copy.deepcopy() of Any values: each kind of value an Any holds is copied as
# that kind's static type is (an object in one is not supported: tests/deviations)
import copy
from typing import Any


def deep(v: Any) -> Any:
    return copy.deepcopy(v)


def shallow(v: Any) -> Any:
    return copy.copy(v)


print(deep(1), deep("s"), deep(None), deep(2.5), deep(True), deep((1, "a")))
print(shallow(1), shallow([1, 2]), shallow({"a": 1}), shallow((1, [2])))
xs: list[Any] = [1, "a", [2, 3], {"k": [4]}, (5, [6])]
ys = copy.deepcopy(xs)
print(ys, ys == xs, ys[2] is not xs[2], ys[3] is not xs[3], ys[4] is not xs[4])
zs = copy.copy(xs)
print(zs[2] is xs[2], zs is not xs)
inner: list[Any] = [7]
pair: list[Any] = [inner, inner, (inner, 1)]
pc = copy.deepcopy(pair)
print(pc[0] is pc[1], pc[0] is not inner)
t = pc[2]
if isinstance(t, tuple):
    print(t[0] is pc[0], t[1])
d: dict[str, Any] = {"a": [1], "b": {"c": 2}, "n": None}
d2 = copy.deepcopy(d)
d["a"].append(9)
print(d2, d2["a"] is not d["a"])
