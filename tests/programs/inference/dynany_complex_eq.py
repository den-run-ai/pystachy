# pystachy: dynamic-any
# == and != of Any values holding complex numbers and numbers of other types: complex's __eq__,
# which compares an int with the real part exactly, and != its inversion
from typing import Any

a: Any = 1 + 0j
b: Any = 1j
c: Any = 1
big: Any = 2 ** 53 + 1
print(a == 1, 1 == a, a != 1, a == 1.0, b == 1, a == c, c == a, b != 2, a == "s", a == None)
print(a == b, a == 1 + 0j, complex(2 ** 53) == big, big == complex(2 ** 53), True == a, a != True)
