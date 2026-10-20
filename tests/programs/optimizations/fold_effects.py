# Platform tests that the compiler decides (sys.platform, os.name, TYPE_CHECKING) inside a larger
# condition: the other operands still run, in CPython's order and only where short-circuiting
# reaches them (issue #4, reproduction A, first).
import os
import sys
from typing import TYPE_CHECKING


def effect() -> bool:
    print("effect")
    return True


if effect() and os.name == "nt":
    print("windows")
else:
    print("posix")


def note(s: str, v: bool) -> bool:
    print("note", s)
    return v


if note("a", False) or sys.platform == "win32":
    print("1 then")
else:
    print("1 else")
if os.name == "nt" or note("b", True):
    print("2 then")
if not (note("c", True) and sys.platform.startswith("win")):
    print("3 then")
if note("d", True) and (note("e", True) and os.name == "nt"):
    print("4 then")
else:
    print("4 else")
for v in [True, False]:
    if note("f", v) or (note("g", v) or os.name == "posix"):
        print("5 then")
if note("h", True) and TYPE_CHECKING:
    print("6 then")
else:
    print("6 else")
x = 3
if x > 5:
    print("7a")
elif note("i", True) and os.name != "posix":
    print("7b")
else:
    print("7c")
if sys.platform == "win32" and note("j", True):
    print("8 then")
if os.name == "posix" and note("k", False):
    print("9 then")
if (note("l", False) and os.name == "nt") or note("m", True):
    print("10 then")
if not TYPE_CHECKING and note("n", True):
    print("11 then")


def f(n: int) -> str:
    if note("o", n > 0) and sys.platform == "win32":
        return "win"
    return "posix"


print(f(1), f(0))
