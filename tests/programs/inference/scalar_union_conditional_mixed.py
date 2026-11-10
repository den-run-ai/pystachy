# A conditional expression whose arms are an int and a float, as the left operand of a binary
# operator whose result is wanted as int | float: the arms make that union, the first boxed at
# its edge once the second is known, and the operation runs on the union (arms of one type keep
# it: scalar_union_conditional_operand.py)
import sys


def mixed(a: int, flag: bool) -> int | float:
    return (a if flag else 1.5) * 2


def mixed_first(a: int, flag: bool) -> int | float:
    return (0.25 if flag else a) + a


def mixed_nested(a: int, x: float, flag: bool) -> int | float:
    return (a if flag else (x if a > 0 else a + 1)) - 1


z = len(sys.argv) - 1
print(mixed(3, True), mixed(3, False), type(mixed(1 + z, False)).__name__, type(mixed(1, z > 0)).__name__)
print(mixed_first(3, True), mixed_first(3 + z, False), mixed_nested(3, 0.5, True), mixed_nested(3, 0.5, False), mixed_nested(-3 - z, 0.5, False))
