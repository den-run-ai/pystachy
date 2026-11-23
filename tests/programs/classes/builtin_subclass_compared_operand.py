# An object of a class that derives from list or dict, compared with an object whose class
# defines the comparison: the method takes the object itself, whose class isinstance() and type()
# tell there, in both operand orders (the reflected call too), for ==, != and the orderings. The
# container's own comparison still answers where no method of the program is called
from dataclasses import dataclass
from typing import NamedTuple


class Stack(list[int]):
    def top(self) -> int:
        return self[-1]


class Table(dict[str, int]):
    pass


class Own(list[int]):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Stack) and other.top() == 3


class OwnTable(dict[str, int]):
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Stack)


class Probe:
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Stack):
            return other.top() == 3
        if isinstance(other, Table):
            return len(other) == 1
        return False


class Named:
    def __eq__(self, other: object) -> bool:
        print("Named.__eq__", type(other).__name__)
        return True


class NeOnly:
    def __ne__(self, other: object) -> bool:
        print("NeOnly.__ne__", type(other).__name__)
        return False


class Ranked:
    def __lt__(self, other: object) -> bool:
        print("Ranked.__lt__", type(other).__name__)
        return isinstance(other, Stack)

    def __gt__(self, other: object) -> bool:
        print("Ranked.__gt__", type(other).__name__)
        return isinstance(other, Stack)


class Pair(NamedTuple):
    a: int

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Stack)


class Plain:
    pass


@dataclass
class Data:
    a: int


s = Stack()
s.append(3)
t = Table()
t["k"] = 1
print(Probe() == s, s == Probe(), Probe() != s, s != Probe(), Probe() == [3], Probe() == t, t == Probe(), t != Probe())
print(Named() == s, s == Named(), Named() != t, t != Named())
print(NeOnly() != s, s != NeOnly(), NeOnly() == s, s == NeOnly())
print(Ranked() < s, s > Ranked(), s < Ranked(), Ranked() > s)
print(Pair(1) == s, s == Pair(1))
print(s == Own(), Own() == s, s != Own(), Own() != s, s == OwnTable(), OwnTable() == s, t == OwnTable(), OwnTable() == t)
print(Plain() == s, s == Plain(), s != Plain(), Data(3) == s, s == Data(3), s == [3], [3] == s, s != [3], t == {"k": 1})
