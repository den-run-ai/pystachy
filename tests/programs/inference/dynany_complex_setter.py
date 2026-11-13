# pystachy: dynamic-any
# isinstance(x, complex) of an Any value makes complex numbers values the dispatchers serve: a
# store to another class's real or imag field still runs, and a complex number's raises CPython's
# AttributeError when it runs.
from typing import Any


class Point:
    def __init__(self, real: float) -> None:
        self.real = real
        self.imag = 0.0


p: Any = Point(1.0)
p.real = 2.0
p.imag = 3.0
print(p.real, p.imag, isinstance(p, complex))
z: Any = 1j
print(isinstance(z, complex))
try:
    z.real = 2.0
except AttributeError as e:
    print("AttributeError:", e)
try:
    z.imag = 2.0
except AttributeError as e:
    print("AttributeError:", e)
print(z)
