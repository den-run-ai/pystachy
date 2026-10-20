# pystachy: dynamic-any
# isinstance(x, int) proves that an Any value holds an int or a bool: arithmetic and comparisons
# on it then read the box's payload as an int, and give what CPython gives for both (a bool's
# results are ints, but for & | ^ of two bools, **, and str() of the value itself).
from typing import Any


def show(xs: list[Any]) -> None:
    total = 0
    for x in xs:
        if isinstance(x, int):
            total += x
            print(x, x + 1, x * 3, x // 2, x % 3, -x, +x, x == 1, x < 2, x >= True, x / 2, x ** 2)
            print(x & 1, x | 0, True & x, x & True, x ^ x, x << 2, x >> 1, not x, bool(x), x != False)
            if x:
                print("true", x)
            if isinstance(x, bool):
                print("bool", x, x + x)
    print(total)


def tenfold(x: Any) -> Any:
    if isinstance(x, int) and x > 1:
        return x * 10
    return x


def rebound(x: Any, y: Any) -> None:
    if isinstance(x, int):
        print(x + 1)
        x = y
        print(x + x)


show([1, True, False, 2.5, "s", 7, -3, 0])
print(tenfold(5), tenfold(True), tenfold("s"), tenfold(1))
rebound(1, "ab")
rebound(2, 0.25)
