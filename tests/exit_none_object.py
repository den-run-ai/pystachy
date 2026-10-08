# sys.exit() of an object that is None at run time is status 0, with no message
import sys


class A:
    pass


def f() -> A | None:
    return None


print("before")
sys.exit(f())
