# An ordering of an object of a class deriving from list (or dict) and a member of an IntEnum,
# IntFlag or StrEnum, with each ordering operator in both operand orders. The member's method
# declines an operand that is no number or member (no str or member for StrEnum, #1745), and the
# object reaches it as itself (#1739), so CPython's TypeError names the operator as written, the
# operands in source order and the object's own class
import enum


class Level(enum.IntEnum):
    LOW = 1


class Bits(enum.IntFlag):
    ONE = 1


class Color(enum.StrEnum):
    RED = "red"


class Stack(list[int]):
    pass


class Table(dict[str, int]):
    pass


def show(label: str, f) -> None:
    try:
        print(label, f())
    except TypeError as e:
        print(label, "TypeError", e)


s = Stack()
s.append(1)
t = Table()
t["a"] = 1
show("Stack < Level", lambda: s < Level.LOW)
show("Level < Stack", lambda: Level.LOW < s)
show("Stack <= Level", lambda: s <= Level.LOW)
show("Level <= Stack", lambda: Level.LOW <= s)
show("Stack > Level", lambda: s > Level.LOW)
show("Level > Stack", lambda: Level.LOW > s)
show("Stack >= Level", lambda: s >= Level.LOW)
show("Level >= Stack", lambda: Level.LOW >= s)
show("Stack < Bits", lambda: s < Bits.ONE)
show("Bits < Stack", lambda: Bits.ONE < s)
show("Stack <= Bits", lambda: s <= Bits.ONE)
show("Bits <= Stack", lambda: Bits.ONE <= s)
show("Stack > Bits", lambda: s > Bits.ONE)
show("Bits > Stack", lambda: Bits.ONE > s)
show("Stack >= Bits", lambda: s >= Bits.ONE)
show("Bits >= Stack", lambda: Bits.ONE >= s)
show("Stack < Color", lambda: s < Color.RED)
show("Color < Stack", lambda: Color.RED < s)
show("Stack <= Color", lambda: s <= Color.RED)
show("Color <= Stack", lambda: Color.RED <= s)
show("Stack > Color", lambda: s > Color.RED)
show("Color > Stack", lambda: Color.RED > s)
show("Stack >= Color", lambda: s >= Color.RED)
show("Color >= Stack", lambda: Color.RED >= s)
show("Table < Level", lambda: t < Level.LOW)
show("Level < Table", lambda: Level.LOW < t)
show("Table >= Level", lambda: t >= Level.LOW)
show("Level >= Table", lambda: Level.LOW >= t)
show("Stack == Level", lambda: s == Level.LOW)
show("Color != Stack", lambda: Color.RED != s)
