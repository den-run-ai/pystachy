# pystachy: dynamic-any
# pystachy: python-int
# A promoting int wider than 64 bits, held as an Any value, takes part in complex arithmetic on
# either side: the reflected operation converts it to float, as CPython's TO_COMPLEX does.
from typing import Any

n: Any = 2**80
z: Any = 1j
print(z + n, n + z)
print(n - z, n * z, n / z)
w: Any = 2 + 0j
print(n ** w)
b: Any = True
s: Any = 3
print(b + z, s - z, s * z, s / z, s ** w)
