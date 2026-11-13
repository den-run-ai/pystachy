# A noninteger Enum member remains a message even if it implements __index__ and __int__.
import sys
from enum import Enum, IntEnum


class Status(IntEnum):
    OK = 0


class Plain(Enum):
    THREE = 3

    def __index__(self) -> int:
        print("unexpected index", flush=True)
        return 0

    def __int__(self) -> int:
        print("unexpected int", flush=True)
        return 0

    def __str__(self) -> str:
        return "plain member message"


def member(n: int) -> Enum:
    if n == 0:
        return Status.OK
    return Plain.THREE


print("message", flush=True)
sys.exit(member(len(sys.argv)))
