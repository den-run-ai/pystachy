# pystachy: dynamic-any
# dict.__or__ may defer to the right operand; dict.__ior__ does not (#810).
from typing import Any


class Right:
    def __ror__(self, other: Any) -> Any:
        print("reflected")
        return 42


right: Any = Right()
d: Any = {"a": 1}
alias = d
print(d | right)
try:
    d |= right
except TypeError as error:
    print(type(error).__name__, error)
print(d, d is alias)
# A left operand without an in-place method still tries the reflected method.
number: Any = 3
number |= right
print(number)
