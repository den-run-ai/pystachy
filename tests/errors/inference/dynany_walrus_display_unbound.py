# error: dynany_walrus_display_unbound.py:9: error: local variable 'z' is read before its first assignment; declare it first (z: T)
# pystachy: dynamic-any
# a display's item that reads a name before a later item's := binds it reads it unbound (CPython's
# UnboundLocalError), as in modules that do not opt in
from typing import Any


def main(x: Any) -> None:
    b = [z, z := x]
    print(b)


main(3)
