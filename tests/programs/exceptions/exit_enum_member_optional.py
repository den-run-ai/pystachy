# raise SystemExit(x) of an IntEnum member that may be None, in a program without try: the
# member's value is the status, as an int's is.
import sys
from enum import IntEnum


class Status(IntEnum):
    OK = 0
    FAILED = 5


def result(n: int) -> Status | None:
    if n > 0:
        return Status.FAILED
    return None


print("checking", flush=True)
raise SystemExit(result(len(sys.argv)))
