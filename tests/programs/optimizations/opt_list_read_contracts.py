# Concrete list reads preserve packed item types; length operations keep their
# owner while executing at the original point. Also run with -listget,-listfast.
from typing import Optional


def stride(xs: list[float]) -> float:
    total = 0.0
    for i in range(1, len(xs), 2):
        total += xs[i]
    return total


def bits(xs: list[bool]) -> int:
    total = 0
    for i in range(len(xs)):
        if xs[i]:
            total += 1
    return total


def nested(xs: list[list[float]]) -> float:
    total = 0.0
    for row in xs:
        for i in range(len(row)):
            total += row[i]
    return total


def nullable(xs: Optional[list[str]]) -> int:
    return len(xs) if xs is not None else -1


def unpack(xs: list[float]) -> None:
    first, *middle, last = xs
    print(first, middle, last)


def live_length(xs: list[float]) -> None:
    before = len(xs)
    xs.append(8.0)
    print(before, len(xs), xs[-1])
    for x in xs:
        print(x, len(xs))
        if x == 2.0:
            xs.pop()


def bounds(xs: list[str], i: int) -> None:
    try:
        print(i, xs[i])
    except IndexError:
        print(i, "IndexError")


print(stride([]), stride([0.0, 1.25, 2.5, 3.75, 5.0]))
print(bits([]), bits([True, False, True, False]))
print(nested([[], [1.25, 2.5], [3.75]]))
print(nullable(None), nullable([]), nullable(["one", "two"]))
unpack([1.25, 2.5, 3.75, 5.0])
live_length([1.0, 2.0, 3.0])
for index in [-4, -3, -1, 0, 2, 3]:
    bounds(["one", "two", "three"], index)
bounds([], -1)
bounds([], 0)
