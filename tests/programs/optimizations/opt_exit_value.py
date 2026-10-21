# sys.exit() of a str | None that holds a str prints it, status 1
import sys


def get(flag: bool) -> str | None:
    return "bye" if flag else None


sys.exit(get(True))
