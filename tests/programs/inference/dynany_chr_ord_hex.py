# pystachy: dynamic-any
# chr(), ord(), hex(), oct() and bin() of Any values: an int, a bool or an object's __index__(),
# and a str of one character for ord(), with CPython's TypeError and ValueError for the others.
from typing import Any


class Code:
    def __index__(self) -> int:
        print("Code.__index__")
        return 9731


class Bad:
    def __index__(self) -> Any:
        return 2.5


def arg(value: Any) -> Any:
    print("argument", type(value).__name__)
    return value


def show(name: str, value: Any) -> None:
    try:
        if name == "chr":
            print(repr(chr(arg(value))))
        elif name == "ord":
            print(ord(arg(value)))
        elif name == "hex":
            print(hex(arg(value)))
        elif name == "oct":
            print(oct(arg(value)))
        else:
            print(bin(arg(value)))
    except (TypeError, ValueError) as error:
        print(type(error).__name__, error)


for value in [65, 9731, True, Code(), -1, 1114112, 2.5, "a", None, Bad()]:
    show("chr", value)
for value in ["A", "☺", "", "ab", 65, None, 2.5]:
    show("ord", value)
for name in ["hex", "oct", "bin"]:
    for value in [255, -255, 0, False, Code(), -9223372036854775807 - 1, 1.5, "f", None]:
        show(name, value)
