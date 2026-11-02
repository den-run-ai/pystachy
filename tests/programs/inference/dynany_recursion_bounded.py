# pystachy: dynamic-any
# pystachy: python-int
# Guard-free clones keep the original promoted-value and hidden-identity ABI.
from typing import Any
import sys


def identity(value: int) -> int:
    return value


def identity_observer(value: int) -> int:
    sys.setrecursionlimit(sys.getrecursionlimit())
    return value


def partial_identity(value: int, observe: bool) -> int:
    if observe:
        return identity_observer(value)
    return identity(value)


def relay(value: int) -> int:
    for i in range(2):
        value = identity(value)
    return value


def pair(value: int) -> tuple[int, int]:
    return (identity(value), identity(value))


def relay_pair(value: int) -> tuple[int, int]:
    return pair(value)


def ordinary_pair(value: int) -> tuple[int, int]:
    return (value, value + 1)


def unpack(value: int) -> int:
    result = 0
    for i in range(2):
        left, right = ordinary_pair(value)
        result = left + right
    return result


wide: Any = 123456789012345678901234567890
small: Any = int("1000")
for value in [small, wide]:
    alias: Any = relay(value)
    result: Any = relay_pair(value)
    print("identity", value is alias)
    print("tuple", value == result[0], result[0] == result[1])
    print("value", alias, unpack(value))
    for observe in [False, True]:
        partial_alias: Any = partial_identity(value, observe)
        print("partial identity", observe, value is partial_alias, value == partial_alias)
