# @global_enum of an enum class binds each member's name in the class's module, aliases too, and
# makes repr() of a member the module's name and the member's (calendar's JANUARY: the module's
# last component), as CPython's calendar and re declare theirs; str() of an Enum's member is its
# name, while an IntEnum's and a StrEnum's keep int's and str's. The decorator's repr() and
# str() replace the class's own.
import enum
from enum import Enum, IntEnum, StrEnum, global_enum, unique
import mods.enum_global_days
from mods.enum_global_days import Day, TUESDAY


@global_enum
class Month(IntEnum):
    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    FIRST = 1


@unique
@enum.global_enum
class Tone(Enum):
    LOW = "l"
    HIGH = "h"

    def __repr__(self) -> str:
        return "never"

    def __str__(self) -> str:
        return "never"

    def loud(self) -> bool:
        return self is HIGH


@global_enum
class Word(StrEnum):
    YES = "yes"
    NO = "no"

    def describe(self) -> str:
        return "word " + self.value


@global_enum
class Shared(Enum):
    def tag(self) -> str:
        return repr(self) + "/" + str(self)


class Side(Shared):
    LEFT = 1
    RIGHT = 2


def quarter(m: Month) -> int:
    return 1 if m <= MARCH else 2


print(JANUARY, repr(FEBRUARY), str(MARCH), MARCH + 1, JANUARY is Month.JANUARY, FIRST is JANUARY, quarter(FEBRUARY))
print(list(Month), Month(2), f"{MARCH}", [repr(m) for m in Month], "%r %s" % (MARCH, MARCH))
print(LOW, repr(HIGH), str(HIGH), HIGH is Tone.HIGH, list(Tone), Tone("l"), f"{LOW}", HIGH.loud(), LOW.loud())
print(YES, repr(NO), str(YES), f"{NO}", YES == "yes", list(Word), Word("no") is NO, YES.describe())
print(Side.LEFT.tag(), repr(Side.RIGHT), str(Side.RIGHT), list(Side))
print(repr(TUESDAY), repr(Day.MONDAY), mods.enum_global_days.first(), repr(mods.enum_global_days.MONDAY), str(TUESDAY), TUESDAY - 1)
