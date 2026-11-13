# sys.exit() of a value typed as Enum that holds no int at run time: the member's str() is
# written to stderr and the status is 1, where an IntEnum member of the same static type is a
# status (exit_enum_member_caught.py).
import sys
from enum import Enum, IntEnum


class Status(IntEnum):
    USAGE = 3


class Plain(Enum):
    NINE = 9


def member(k: int) -> Enum:
    if k == 0:
        return Status.USAGE
    return Plain.NINE


print("start", flush=True)
sys.exit(member(len(sys.argv)))
