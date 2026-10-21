# dict.fromkeys(xs, v): each item of xs, in order and once, mapped to the same v (None without
# one, where the dict's annotated values can be None). A dict's keys go into a table sized for
# them at once, any other iterable's one by one, as CPython makes them.
from typing import Iterator


class Bag:
    def __init__(self, items: list[str]) -> None:
        self.items = items

    def __iter__(self) -> Iterator[str]:
        print("iter")
        return iter(self.items)


def val(v: int) -> int:
    print("value")
    return v


print(dict.fromkeys(["x", "y", "x", "z"], 0))
print(dict.fromkeys("hello", 1), dict.fromkeys("", 1))
print(dict.fromkeys(range(3, 0, -1), "v"))
src = {"b": 2, "a": 1, "c": 3}
del src["a"]
print(dict.fromkeys(src, 0), dict.fromkeys(src.keys(), 0))
print(dict.fromkeys(Bag(["p", "q"]), val(5)))
print(dict.fromkeys([(1, "a"), (2, "b"), (1, "a")], 0.5))
shared = dict.fromkeys([1, 2, 3], [0])
shared[1].append(1)
print(shared)
n: dict[str, int | None] = dict.fromkeys(["a", "b"])
n["a"] = 1
print(n, dict.fromkeys(["c"], n["a"]))
m: dict[int, str | None] = dict.fromkeys([3, 1, 2], None)
print(m)
e: dict[str, list[int]] = dict.fromkeys([], [])
print(e, dict.fromkeys(e, 0))


def first(xs, v):
    # a template: the keys' and the value's types come from each call
    return dict.fromkeys(xs, v)


print(first([1, 2], "one"), first("ab", 2.5))

# an empty iterable makes an empty dict; a missing iterable is CPython's TypeError, raised once
# the value is evaluated
xs: list[str] | None = None
try:
    print(dict.fromkeys(xs, val(7)))
except TypeError as x:
    print("TypeError:", x)
