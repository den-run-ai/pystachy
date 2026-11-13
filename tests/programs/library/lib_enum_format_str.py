# format() of an IntEnum, a StrEnum or an IntFlag member is int's or str's: with an empty format
# spec that is str() of the member, so a class's own __str__ shows in an f-string, format() and
# str.format() as it does in str() and %s; a spec formats the member's value
from enum import Enum, IntEnum, IntFlag, StrEnum


class Word(StrEnum):
    YES = "yes"

    def __str__(self) -> str:
        return "kept:" + self.value


class Num(IntEnum):
    ONE = 1

    def __str__(self) -> str:
        return "one!"


class Perm(IntFlag):
    R = 4
    W = 2

    def __str__(self) -> str:
        return "perm(%d)" % self.value


class Plain(Enum):
    A = 1

    def __str__(self) -> str:
        return "plain!"


class Level(IntEnum):
    LOW = 1


class Tone(StrEnum):
    SOFT = "soft"


print(f"{Word.YES}", format(Word.YES), "{}".format(Word.YES), str(Word.YES), "%s" % Word.YES, f"{Word.YES:>5}", f"{Word.YES!r}")
print(f"{Num.ONE}", format(Num.ONE), "{}".format(Num.ONE), str(Num.ONE), "%s" % Num.ONE, f"{Num.ONE:d}", f"{Num.ONE:03}")
print(f"{Perm.R}", format(Perm.R | Perm.W), "{}".format(Perm.W), str(Perm.R), f"{Perm.R:x}", f"{Perm.R | Perm.W:>4}")
print(f"{Plain.A}", format(Plain.A), "{}".format(Plain.A), str(Plain.A), "%s" % Plain.A, f"{Plain.A:>8}")
print(f"{Level.LOW}", format(Level.LOW), "{}".format(Level.LOW), f"{Level.LOW:>3}", f"{Tone.SOFT}", format(Tone.SOFT), f"{Tone.SOFT:_<6}")
print([f"{m}" for m in Word], [format(m, "") for m in Num], "{0} {0:d}".format(Num.ONE))
