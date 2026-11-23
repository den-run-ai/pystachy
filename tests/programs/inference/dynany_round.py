# pystachy: dynamic-any
# round() of Any values: an int stays itself where no digits are dropped, a float rounds half to
# even, an object's __round__ runs (without arguments for an ndigits of None, as CPython calls it),
# an ndigits is taken by its __index__(), and CPython's errors come in CPython's order.
from typing import Any


class Price:
    def __init__(self, value: float) -> None:
        self.value = value

    def __round__(self, ndigits: Any = None) -> Any:
        print("Price.__round__", ndigits)
        return "price" if ndigits is None else round(self.value, ndigits)


class Whole:
    def __round__(self) -> int:
        print("Whole.__round__")
        return 7


class Digits:
    def __index__(self) -> int:
        print("Digits.__index__")
        return 1


def arg(label: str, value: Any) -> Any:
    print("argument", label)
    return value


def one(x: Any) -> None:
    try:
        print(round(arg("x", x)))
    except (TypeError, ValueError, OverflowError) as error:
        print(type(error).__name__, error)


def two(x: Any, n: Any) -> None:
    try:
        print(round(arg("x", x), arg("n", n)))
    except (TypeError, ValueError, OverflowError) as error:
        print(type(error).__name__, error)


for x in [3, -3, True, 2.5, 3.5, -0.5, 1e15 + 0.5, float("nan"), float("inf"), "a", None, Price(2.5), Whole()]:
    one(x)
for x, n in [(1234, -2), (1250, -2), (1350, -2), (7, 0), (7, 3), (True, -1), (2.675, 2), (1234.5, -2), (2.5, None),
             (2.5, 1.5), (2.5, "1"), ("a", 1.5), (None, 2), (2.5, Digits()), (17, Digits()), (Price(2.5), 1), (Price(2.5), None),
             (Whole(), 1), (Whole(), None), (2.5, True)]:
    two(x, n)

big: Any = 1000
print(round(big) is big, round(big, 2) is big, round(big, -1) is big)
flag: Any = True
print(round(flag), type(round(flag)).__name__)
ndigits: Any = 1
print(round(2.25, ndigits), round(25, -1), round(3, ndigits))
