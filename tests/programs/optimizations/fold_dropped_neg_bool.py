# A local that only a dropped Windows branch binds, to -True: its type is int, as -True is -1,
# so an int variable may take it, and the read raises UnboundLocalError where it runs.
import sys


def f() -> None:
    if sys.platform == "win32":
        x = -True
    print("before")
    y: int = x
    print(y)


f()
