# error: three-argument object pow() requires concrete native operand types
# pystachy: dynamic-any
from typing import Any


class Power:
    def __pow__(self, other, modulus: int) -> int:
        return modulus


class Exponent:
    pass


base: Any = Power()
print(pow(base, Exponent(), 5))
