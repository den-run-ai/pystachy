# error: 'sqrt' is bound both by an import and by a def or class
from math import sqrt
print(sqrt(16.0))


def sqrt(x: float) -> float:
    return x + 1.0
