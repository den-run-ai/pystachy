# Catching preserves enum str/repr while exit status ignores integer conversion overrides.
import sys
from enum import Enum, IntEnum


class Status(IntEnum):
    OK = 0
    FAILED = 3

    def __index__(self) -> int:
        raise AssertionError("index must not decide an exit status")

    def __int__(self) -> int:
        raise AssertionError("int must not decide an exit status")

    def __str__(self) -> str:
        return "status " + str(self.value)


class Mixed(int, Enum):
    FOUR = 4

    def __index__(self) -> int:
        raise AssertionError("mixed index must not run")

    def __str__(self) -> str:
        return "mixed status"


class Quit(SystemExit):
    pass


def member(n: int) -> Enum | None:
    if n == 0:
        return Status.OK
    if n == 1:
        return Status.FAILED
    if n == 2:
        return Mixed.FOUR
    return None


for i in range(4):
    try:
        sys.exit(member(i))
    except SystemExit as e:
        print(i, str(e), repr(e))
    try:
        saved = SystemExit(member(i))
        raise saved
    except SystemExit as e:
        print("saved", i, str(e), repr(e))
try:
    raise Quit(Status.FAILED)
finally:
    print("finally", flush=True)
