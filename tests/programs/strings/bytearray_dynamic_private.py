# pystachy: dynamic-any
# A bytearray held as an Any value has its methods and no attribute of its own, as CPython's: the
# fields and helpers of lib's class are not its attributes.
from typing import Any


def main() -> None:
    xs: list[Any] = [bytearray(b"abc"), 1]
    try:
        print(xs[0]._n)
    except AttributeError as e:
        print("AttributeError:", e)
    try:
        print(xs[0]._getslice(0, 1, None))
    except AttributeError as e:
        print("AttributeError:", e)
    print(xs[0].upper(), len(xs[0]))


main()
