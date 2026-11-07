# pystachy: dynamic-any
from typing import Any


def identical(left: Any, right: Any) -> bool:
    return left is right


def constants() -> list[float]:
    return [1000.25, 1000.25, -0.0, 0.0, 1.0, 2.0, 3.0, 4.0,
            5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0,
            13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0,
            21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0]


a = constants()
b = constants()
print(a is b, identical(a[0], a[1]), identical(a[0], b[0]), identical(a[2], b[2]), identical(a[2], a[3]))
copy = a.copy()
a[0] = 2000.5
print(identical(copy[0], b[0]), identical(copy[0], a[0]), b[0])

x: Any = float("nan")
y: Any = float("nan")
values: list[float] = [x, y, x, y, x, y, x, y, x, y, x, y, x, y, x, y,
                       x, y, x, y, x, y, x, y, x, y, x, y, x, y, x, y]
print(len(values), identical(values[0], x), identical(values[1], y), identical(values[0], values[2]))
print(values.count(x), values.count(y), x in values, y in values)
alias = values
values.reverse()
print(identical(alias[0], y), identical(alias[1], x), alias is values)
