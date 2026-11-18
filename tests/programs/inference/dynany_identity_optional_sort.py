# pystachy: dynamic-any
# Sorting lists of optional numbers whose items keep their identities (#1502): values order the
# items (not their boxes), equal items keep their order and identity, reverse= and key= agree,
# and a None that cannot be compared raises CPython's error and leaves the list in the order
# the sort reached.
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b


def ints(xs: list[int | None]) -> None:
    print("sorted", sorted(xs), sorted(xs, reverse=True), min(xs), max(xs))
    ys = list(xs)
    ys.sort()
    print("sort", ys)
    ys.sort(reverse=True)
    print("reverse", ys)
    print("key", sorted(xs, key=lambda v: 0 if v is None else -v))


def floats(xs: list[float | None]) -> None:
    ys = list(xs)
    ys.sort()
    print("floats", sorted(xs), sorted(xs, reverse=True), ys)


def nans(text: str) -> None:
    xs: list[float | None] = [3.0, float(text), 1.0, 2.0, 0.5]
    print("nan", sorted(xs), sorted(xs, reverse=True))


def stable(text: str) -> None:
    first: Any = int(text)
    second: Any = int(text)
    a: int | None = first
    b: int | None = second
    xs: list[int | None] = [a, 3, b, 2]
    ys = sorted(xs)
    print("stable", ys, same(ys[2], first), same(ys[3], second), same(ys[2], second))
    xs.sort(reverse=True)
    print("stable reverse", xs, same(xs[0], first), same(xs[1], second))


def failed(xs: list[int | None], reverse: bool) -> None:
    try:
        xs.sort(reverse=reverse)
    except TypeError as e:
        print("TypeError:", e)
    print("after", xs)


def failed_floats(xs: list[float | None]) -> None:
    try:
        print(sorted(xs))
    except TypeError as e:
        print("TypeError:", e)
    try:
        xs.sort()
    except TypeError as e:
        print("TypeError:", e)
    print("after", xs)


def merged(n: int) -> None:
    xs: list[int | None] = []
    v = 7
    for i in range(n):
        v = (v * 1103515245 + 12345) % 2147483648
        xs.append(v % 1000)
    ys = sorted(xs)
    total = 0
    for i, y in enumerate(ys):
        if y is not None:
            total += i * y
    print("merged", len(ys), ys[:5], ys[-5:], total)
    xs.sort(reverse=True)
    print("merged reverse", xs[:5], xs[-5:])


ints([3, 1, 20, -4, 1, 7])
floats([2.5, -1.0, 9.75, 0.0, 2.5])
nans("nan")
stable("1000")
failed([2, 1, 3, None], False)
failed([5, 4, 3, 9, 8, None, 1], False)
failed([1, 2, 7, None, 3], True)
failed_floats([2.5, 1.5, 3.5, None])
merged(200)
