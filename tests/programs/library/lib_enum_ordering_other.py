# An ordering of a value that has none with an int or a str (a list, an object of a class deriving
# from list, a str beside an int enum, None) and a member of an IntEnum, IntFlag or StrEnum, in
# both operand orders: the member's method declines, as int's and str's do, and CPython's
# TypeError names the operator as written and the operands in source order (#1745). The
# orderings that int and str do have still answer
import enum


class Level(enum.IntEnum):
    LOW = 1
    HIGH = 2


class Bits(enum.IntFlag):
    ONE = 1


class Color(enum.StrEnum):
    RED = "red"


class Stack(list[int]):
    pass


def show(label: str, f) -> None:
    try:
        print(label, f())
    except TypeError as e:
        print(label, "TypeError", e)


s = Stack()
s.append(1)
show("list < Level", lambda: [1] < Level.LOW)
show("list <= Level", lambda: [1] <= Level.LOW)
show("list > Level", lambda: [1] > Level.LOW)
show("list >= Level", lambda: [1] >= Level.LOW)
show("Level < list", lambda: Level.LOW < [1])
show("Level >= list", lambda: Level.LOW >= [1])
show("str < Level", lambda: "a" < Level.LOW)
show("str <= Level", lambda: "a" <= Level.LOW)
show("str > Level", lambda: "a" > Level.LOW)
show("str >= Level", lambda: "a" >= Level.LOW)
show("Level > str", lambda: Level.LOW > "a")
show("Stack < Level", lambda: s < Level.LOW)
show("Stack <= Level", lambda: s <= Level.LOW)
show("Stack > Level", lambda: s > Level.LOW)
show("Stack >= Level", lambda: s >= Level.LOW)
show("Level <= Stack", lambda: Level.LOW <= s)
show("list < Bits", lambda: [1] < Bits.ONE)
show("list >= Bits", lambda: [1] >= Bits.ONE)
show("str > Bits", lambda: "a" > Bits.ONE)
show("Bits < list", lambda: Bits.ONE < [1])
show("Stack <= Bits", lambda: s <= Bits.ONE)
show("list < Color", lambda: [1] < Color.RED)
show("int >= Color", lambda: 1 >= Color.RED)
show("Color < list", lambda: Color.RED < [1])
show("Color > int", lambda: Color.RED > 1)
show("Level < Level", lambda: Level.LOW < Level.HIGH)
show("int < Level", lambda: 0 < Level.LOW)
show("float >= Level", lambda: 1.5 >= Level.LOW)
show("Level < Bits", lambda: Level.LOW < Bits.ONE)
show("str < Color", lambda: "a" < Color.RED)
show("None < Level", lambda: None < Level.LOW)
show("Level < None", lambda: Level.LOW < None)
