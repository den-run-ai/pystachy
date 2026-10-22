# pystachy: dynamic-any
# A float literal can reach an int slot before a compilation restart widens its type.
# Literal identity follows the source type, never the provisional destination type.
import math
from typing import Any


def pick(flag: bool):
    value = 300
    if flag:
        value = 2.5
    return value


def reverse(flag: bool):
    value = -2.5
    if flag:
        value = -300
    return value


for flag in [False, True]:
    a = pick(flag)
    b = reverse(flag)
    print(a, int(a), round(a), math.floor(a), math.ceil(a), math.trunc(a))
    print(b, int(b), round(b), math.floor(b), math.ceil(b), math.trunc(b))

global_value = 3
if bool(int("1")):
    global_value = 2.5
print("global", global_value, int(global_value), round(global_value))


def same(label: str, a: Any, b: Any) -> None:
    print(label, a, b, a is b, id(a) == id(b))


same("int result", int(1000.5), 1000)
same("round result", round(1000.5), 1000)
same("floor result", math.floor(1000.5), 1000)
same("ceil result", math.ceil(999.5), 1000)
same("trunc result", math.trunc(1000.5), 1000)
same("float result", float(1000), 1000.0)
same("abs result", abs(-1.5), 1.5)
same("round float result", round(1.5, 1), 1.5)
left = right = 1.5
same("chained literal", left, right)
left = right = float("1.5")
same("chained computed", left, right)
