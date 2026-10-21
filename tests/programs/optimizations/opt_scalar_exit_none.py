# sys.exit() of an int | None that is None exits with status 0, after what the program printed
import sys


def use(n: int | None) -> None:
    print("using", repr(n))
    sys.exit(n)


use(None)
