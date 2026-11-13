# sys.exit() and SystemExit of enum members in a program with try. The members of IntEnum and
# IntFlag classes, and of a class of int and Enum, are CPython's ints: the status, shown by
# str(e) as the member's str(). Another enum's member is a message, shown with status 1. The
# class of the object decides where the value is typed as their base, Enum.
import sys
from enum import Enum, IntEnum, IntFlag


class Status(IntEnum):
    OK = 0
    USAGE = 3
    WIDE = 259


class Perm(IntFlag):
    R = 4
    W = 2


class Mixed(int, Enum):
    SEVEN = 7


class Plain(Enum):
    NINE = 9


def member(k: int) -> Enum:
    if k == 0:
        return Status.USAGE
    if k == 1:
        return Plain.NINE
    if k == 2:
        return Perm.R | Perm.W
    return Mixed.SEVEN


def run(k: int) -> None:
    try:
        if k == 0:
            sys.exit(Status.USAGE)
        elif k == 1:
            raise SystemExit(Perm.R | Perm.W)
        elif k == 2:
            sys.exit(Mixed.SEVEN)
        elif k == 3:
            sys.exit(Status.OK)
        elif k == 4:
            sys.exit(Plain.NINE)
        elif k == 5:
            sys.exit(Perm(0))
        elif k < 10:
            sys.exit(member(k - 6))
        else:
            e = SystemExit(member(k - 10))
            raise e
    except SystemExit as e:
        print(k, str(e), repr(e))
    finally:
        print("finally", k)


for i in range(14):
    run(i)
try:
    sys.exit(Status.WIDE)
finally:
    print("last", flush=True)
