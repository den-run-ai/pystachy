# sys.exit() of an int | None exits with the int's status, and of None with status 0
# (opt_scalar_exit_none.py)
import sys


def use(n: int | None) -> None:
    print("using", repr(n))
    sys.exit(n)


use(3)
