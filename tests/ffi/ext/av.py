import sys
from ffi import export


@export
def nargs() -> int:
    return len(sys.argv)


@export
def warnoptions() -> str:
    return repr(sys.warnoptions)  # (the host's: tests/ffi/run.sh runs it with -W ignore)


@export
def say(s: str) -> None:
    print(s)
