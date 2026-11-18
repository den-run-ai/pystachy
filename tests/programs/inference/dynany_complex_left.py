# pystachy: dynamic-any
# A complex number on the right of a value that is not a number, both held as Any values: complex
# declines it, so the TypeError is CPython's for the left operand's type.
from typing import Any


class Left:
    pass


z: Any = 1j
for x in ["a", [1], (1,), None, Left()]:
    v: Any = x
    for op in ["+", "-", "*", "/", "**"]:
        try:
            if op == "+":
                print(v + z)
            elif op == "-":
                print(v - z)
            elif op == "*":
                print(v * z)
            elif op == "/":
                print(v / z)
            else:
                print(v ** z)
        except TypeError as e:
            print("TypeError:", e)
