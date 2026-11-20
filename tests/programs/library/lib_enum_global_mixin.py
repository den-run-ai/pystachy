# @global_enum of an enum class of int or str and Enum, which is no ReprEnum: str() and format()
# of a member are its name (CPython's global_str), replacing the class's own __str__, while
# repr() names the module and the member and the member keeps int's or str's operations.
from enum import Enum, global_enum


@global_enum
class Code(int, Enum):
    OK = 0
    BAD = 1

    def __str__(self) -> str:
        return "never"


@global_enum
class Word(str, Enum):
    HI = "hi"
    LO = "lo"


print(str(OK), repr(BAD), f"{BAD}", "%s" % OK, OK + 1, BAD == 1)
print(str(HI), repr(LO), format(HI, ">4"), HI + "!", HI == "hi", list(Word))
