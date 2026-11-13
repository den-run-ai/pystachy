# Exception classes deriving from SystemExit whose code is an enum member: an IntEnum member
# is CPython's int, the status the program ends with if nothing catches the exception; another
# enum's member or None is not.
import sys
from enum import Enum, IntEnum


class Status(IntEnum):
    USAGE = 3


class Plain(Enum):
    NINE = 9


class Quit(SystemExit):
    pass


class Stop(Quit):
    def __init__(self, why: str, code: Enum | None) -> None:
        super().__init__(code)
        self.why = why


def member(k: int) -> Enum | None:
    if k == 0:
        return Status.USAGE
    if k == 1:
        return Plain.NINE
    return None


for i in range(3):
    try:
        raise Stop("w" + str(i), member(i))
    except Stop as e:
        print(i, e.why, str(e), repr(e))
try:
    raise Quit(Status.USAGE)
except Quit as e:
    print(str(e), repr(e))
print("end", flush=True)
raise Stop("last", member(len(sys.argv) - 3))
