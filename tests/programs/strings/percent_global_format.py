# % formatting of a module global that a single assignment binds to a string literal (a
# Final one too): the literal's conversions, once the name is read (a read before the assignment
# raises NameError, as in CPython), and the format read before its arguments, also through a
# from-import and another module's attribute; a class attribute's type is inferred from it
from typing import Final

import mods.fmtconstants as fc
from mods.fmtconstants import PCT

FMT: Final = "%d items"
PAIR = "%s=%r"


def count(n: int) -> str:
    return FMT % n


def arg(v: str) -> str:
    print("arg", v)
    return v


def early() -> str:
    return LATER % 1.5


try:
    print(early())
except NameError as e:
    print("NameError:", e)
LATER = "%.3f|%5.1e"
try:
    print(early())
except TypeError as e:
    print("TypeError:", e)
print(count(3), PAIR % (arg("k"), arg("v")), PCT % ("ab", 7), fc.PCT % ("c", 8))
try:
    print(PAIR % ("only",))
except TypeError as e:
    print("TypeError:", e)


class Labels:
    total = FMT % 2
    pair = "%s/%s" % ("a", "b")


print(Labels.total, Labels.pair)
