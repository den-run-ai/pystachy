# Values of object holding objects of library classes whose comparison takes only their own kind
# (range, a deque, a date, a timedelta, a time), beside an IntEnum's and an Enum's member, whose
# class's method CPython calls first, dataclass objects, an object whose __eq__ returns
# NotImplemented, a str, an int and None: each declines what is not of its kind, as CPython's
# types do, so that the other operand's method, else identity, answers, and equal objects of one
# kind are equal
import collections
import datetime
import enum
from dataclasses import dataclass


class Level(enum.IntEnum):
    LOW = 1


class Tone(enum.Enum):
    A = 1


@dataclass
class Point:
    x: int


@dataclass(eq=False)
class Plain:
    x: int


class Shy:
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Shy):
            return True
        return NotImplemented


def same(a: object, b: object) -> bool:
    return a == b


def differ(a: object, b: object) -> bool:
    return a != b


def main() -> None:
    values: list[object] = [
        range(1), range(1), range(0), range(5, 5),
        collections.deque([1]), collections.deque([1]),
        datetime.date(2020, 1, 1), datetime.date(2020, 1, 1), datetime.timedelta(1),
        datetime.time(5), datetime.datetime(2020, 1, 1),
        Level.LOW, Tone.A, Point(1), Plain(1), Shy(), "s", 1, None,
    ]
    names = ["range(1)", "range(1)b", "range(0)", "range(5,5)", "deque", "deque b", "date", "date b", "timedelta", "time", "datetime", "LOW", "A", "Point", "Plain", "Shy", "'s'", "1", "None"]
    for i in range(len(values)):
        row = ""
        for j in range(len(values)):
            e = same(values[i], values[j])
            n = differ(values[i], values[j])
            row += "=" if e and not n else "." if n and not e else "?"
        print(names[i].ljust(10), row)


main()
