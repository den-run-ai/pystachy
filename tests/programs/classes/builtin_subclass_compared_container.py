# An object of a class that derives from list or dict, compared with an object of a class whose
# comparison method compiles only for the container: one whose parameter is annotated with the
# container's type, or whose code needs a container or does not compile for None (the object of
# a module's variable may be None to the compiler). The method takes the container, as it did
# before objects were passed as themselves (builtin_subclass_compared_operand.py), and each
# program below prints what CPython prints. A class that defines __eq__ but not __ne__ keeps the
# container's !=, which declines an operand that is no such container: the other operand's
# method, else identity, answers, and the class's __eq__ is not asked
class Stack(list[int]):
    pass


class Table(dict[str, int]):
    pass


class Own(list[int]):
    def __eq__(self, other: object) -> bool:
        return True


class OwnTable(dict[str, int]):
    def __eq__(self, other: object) -> bool:
        return True


class Bare:
    def __eq__(self, other):
        return len(other) == 2 and other[0] == 3


class BareKeys:
    def __eq__(self, other):
        return len(other) == 1 and other["k"] == 3


class Typed:
    def __eq__(self, other: list[int] | None) -> bool:
        return other is not None and len(other) == 2


class Keyed:
    def __eq__(self, other: dict[str, int] | None) -> bool:
        return other is not None and len(other) == 1


def total(xs: list[int]) -> int:
    return sum(xs)


class Summed:
    def __eq__(self, other):
        return other is not None and total(other) == 4

    def __ne__(self, other):
        return other is not None and sorted(other) == [1, 3]


class Probe:
    def __eq__(self, other: object) -> bool:
        return False


class NeOnly:
    def __ne__(self, other: object) -> bool:
        return True


class Declines:
    def __eq__(self, other: object) -> bool:
        return NotImplemented


s = Stack()
s.append(3)
s.append(1)
t = Table()
t["k"] = 3
print(s == Bare(), s != Bare(), Bare() == s, Bare() != s)
print(t == BareKeys(), t != BareKeys(), BareKeys() == t)
print(s == Typed(), Typed() == s, s != Typed(), Typed() != s)
print(t == Keyed(), Keyed() == t, t != Keyed())
print(s == Summed(), Summed() == s, s != Summed(), Summed() != s)
print(Own() != Probe(), Own() != NeOnly(), Declines() != Own(), Probe() != Own(), Own() == Probe())
print(OwnTable() != Probe(), OwnTable() != NeOnly(), Declines() != OwnTable(), Probe() != OwnTable())
print(Own() != Own(), Own() != [1], [1] != Own(), OwnTable() != OwnTable(), OwnTable() != {"k": 1})


def local() -> None:
    a = Stack()
    a.append(3)
    a.append(1)
    b = Table()
    b["k"] = 3
    print(a == Bare(), Bare() != a, b == BareKeys(), a == Typed(), Keyed() == b, a == Summed())
    print(Own() != Probe(), Declines() != Own(), OwnTable() != NeOnly())


local()
