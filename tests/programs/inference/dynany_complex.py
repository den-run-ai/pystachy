# pystachy: dynamic-any
# complex numbers as dynamic values: an Any holds the object, whose operations are its class's,
# also with an int, a float or a bool on the left
from typing import Any

z = complex(1, 2)
x: Any = z
print(x, type(x).__name__, isinstance(x, complex), isinstance(x, (int, float)), x == complex(1, 2), x is z)
items: list[Any] = [1, 2.5, 3j, "s", True]
print(items, [type(i).__name__ for i in items], [isinstance(i, complex) for i in items])
y: Any = 3j
print(y.imag, y.real, hash(y) == hash(3j), y.conjugate(), abs(y), bool(y), -y, +y)
w: complex = y
print(w * w, x + 1, x + 2.5, x + x, x * x, x - 1, x / 2, x ** 2, x ** x == z ** z)
print(2 * x, 2.5 + x, 1 / x, 1 - x, True * x, 2 ** y == 2 ** 3j, 3.0 - y)
print(x == 1, 1 == x, x != 2.0, x == x, y == 3j, 3j == y, repr(x), str(y), f"{x} {y!r}")
d: dict[Any, Any] = {3j: "i", 1: "one"}
print(d[3j], d[complex(0, 3)], complex(1, 0) in d, complex(2, 0) in d, d)
total: Any = 0j
for item in [1, 2.5, 3j]:
    total = total + item
print(total)
