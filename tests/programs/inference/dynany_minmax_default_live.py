# pystachy: dynamic-any
# A dynamic iterable stays live while min/max calls the key. Neither the default nor a
# non-existent item is passed to the key; a boxed None item is not the end-of-iteration marker.
from typing import Any

xs: Any = [1, 2]


def grow(x: Any) -> Any:
    if x == 1:
        xs.append(3)
    return x


print(max(xs, key=grow, default=0), xs)
native: list[int] = [1, 2]
xs = native
print(max(xs, key=grow, default=0), native)
xs = [2, 1]


def lower(x: Any) -> Any:
    if x == 2:
        xs.append(0)
    return x


print(min(xs, default=0, key=lower), xs)
xs = [1, 2]


def clear(x: Any) -> Any:
    xs.clear()
    return x


print(max(xs, key=clear, default=-1), xs)
xs = [3, 1, 2]
no_key: Any = None
print(max(xs, key=no_key, default=0), min(xs, default=0, key=None))


def negative(x: Any) -> Any:
    return -x


some_key: Any = negative
print(max(xs, key=some_key, default=0), max(xs, key=no_key, default=0))
fallback: Any = []
empty: Any = []
print(max(empty, default=fallback) is fallback)


def no_calls(x: Any) -> Any:
    raise ValueError("the empty iterable called its key")


print(min(empty, key=no_calls, default="empty"), max(empty, key=no_key, default="empty"))
invalid: Any = 7
print(max(empty, key=invalid, default="empty"))
try:
    max(xs, key=invalid, default=0)
except TypeError as e:
    print("TypeError", e)
one: Any = [None]
print(max(one, default=0), min(one, key=lambda x: 1, default=0))


class Unsized:
    def __iter__(self):
        return iter([7, 4])

    def __len__(self) -> int:
        raise ValueError("min/max asked for a length hint")


bag: Any = Unsized()
print(max(bag, default=0), min(bag, default=0))
