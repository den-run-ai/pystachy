import sys
from ffi import export


@export
def nargs() -> int:
    return len(sys.argv)


@export
def say(s: str) -> None:
    print(s)
