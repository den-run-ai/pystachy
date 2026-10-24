# pystachy: dynamic-any
from typing import Any


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


same("add", 999 + 1, 1000)
same("subtract", 1001 - 1, 1000)
same("multiply", 40 * 25, 1000)
same("floor divide", 3001 // 3, 1000)
same("remainder", 3001 % 2001, 1000)
same("power", 10 ** 3, 1000)
same("left shift", 125 << 3, 1000)
same("right shift", 8001 >> 3, 1000)
same("bit and", 1023 & 1000, 1000)
same("bit or", 992 | 8, 1000)
same("bit xor", 1023 ^ 23, 1000)
same("invert", ~-1001, 1000)
same("nested sign", -(500 + 500), -1000)
same("nested operators", (15 + 5) * (20 + 30), 1000)
same("minimum", -9223372036854775807 - 1, -9223372036854775808)
same("negative floor", -3001 // 3, -1001)
same("negative modulo", 1000 % -3000, -2000)
runtime = int("999")
same("runtime operand", runtime + 1, 1000)
same("runtime equal results", runtime + 1, runtime + 1)
same("conversion call", int("1000"), 1000)
same("power outside fold bound", 1 ** 1000, 1)


def twice() -> Any:
    return 990 + 10


same("repeated folded return", twice(), twice())
same("folded return literal", twice(), 1000)
for attempt in range(2):
    try:
        result: Any = 1000 // 0
        print(result)
    except ZeroDivisionError:
        print("division still raises", attempt)
try:
    result = 1000 << -1
    print(result)
except ValueError:
    print("negative shift still raises")
