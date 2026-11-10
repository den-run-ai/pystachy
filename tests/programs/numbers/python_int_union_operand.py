# pystachy: python-int
# A conditional or boolean expression as the left operand of a binary operator, where the
# result is wanted as a closed union, in a module of promoting ints: arms that are promoting
# ints, or one of them and a 64-bit int, keep the promoting int, and the operation runs on it
# (the union's own int member stays 64-bit: docs/python-int.md)
import sys


def both(a: int, c: int) -> int | str:
    return (a if a > 0 else c) * 2


def literal_else(a: int) -> int | str:
    return (a if a > 0 else 0) * 2 + 1


def literal_then(a: int) -> int | str:
    return (1 if a > 0 else a) * 2


def boolean(a: int, c: int) -> int | str:
    return ((a if a > 0 else c) or 7) * 2


def bits(a: int, c: int) -> int | float:
    return (a if a > 0 else c) & 0xFF


def masked(a: int, c: int) -> int | str:
    return ((a if a > 0 else c) * 2654435761 + c) & 0xFFFFFFFF


def wide(a: int, c: int) -> int | str:
    # (an intermediate result past 64 bits is exact: the cube is a promoting int)
    return (a if a > 0 else c) ** 3 // 10**12


z = len(sys.argv) - 1
print(both(3 + z, 4), both(-3, 4 + z), literal_else(3 + z), literal_else(-3), literal_then(3), literal_then(-3 - z))
print(boolean(3, 4), boolean(0, z - 2), bits(3, 4), bits(-3, 300 + z), masked(123456789, 5), wide(10**9 + z, 2), wide(-1, 20000 + z))
