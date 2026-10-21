# pystachy: dynamic-any
# | and |= of Any values that hold dicts: | makes a new dict of the left one's items updated with
# the right one's, as dict.__or__ does; |= updates the dict in place, so every name of it sees the
# change, with a mapping or pairs, as dict.update() does, with its errors (#810)
from typing import Any

d: Any = {"a": 1, "b": 2}
e: Any = {"b": 20, "c": 3}
alias = d
u = d | e
print(u, d, e, u is d, u is e)
d |= e
print(d, alias, alias is d)
d |= [("x", 7), ["y", 8]]
print(d)
d |= {1: "one", (2, 3): "pair"}
print(d)
g: Any = {}
g |= ["ab"]
print(g)
bads: list[Any] = [True, [1], ["abc"], [("k",)], "ab"]
for bad in bads:
    f: Any = {"keep": 0}
    try:
        f |= bad
    except (TypeError, ValueError) as x:
        print(type(x).__name__, x, f)
try:
    print(d | [("z", 1)])
except TypeError as x:
    print("TypeError", x)
p: Any = [("z", 1)]
try:
    print(p | d)
except TypeError as x:
    print("TypeError", x)
xs: list[Any] = [{"a": 1}]
first = xs[0]
xs[0] |= {"b": 2}
print(xs, first is xs[0])


def merged(left: Any, right: Any) -> Any:
    return left | right


print(merged({"k": 1}, {"k": 2, "j": 3}), merged({}, {}))
