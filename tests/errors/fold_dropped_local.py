# error: 'x' is local to f() only through code that is dropped at compile time
import sys

x = 5


def f() -> int:
    if sys.platform == "win32":
        x = 1
    return x


print(f())
