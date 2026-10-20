# x in t compares x with each item of the tuple by ==, in order, and stops at the first that is
# equal (#320): an item of another type than x's is equal where its class's __eq__(x) says so,
# or, where its class defines none (a builtin type's declines), where x's __eq__(item) says so.
# Items of other types with no __eq__ to call are not equal, as before. CPython's
# seq_tests.CommonTest.test_contains_fake and test_contains_order test the same.
from dataclasses import dataclass
from typing import NamedTuple


class AlwaysEq:
    def __eq__(self, other) -> bool:
        return True


class NeverEq:
    def __eq__(self, other) -> bool:
        return False


class StopCompares:
    def __eq__(self, other) -> bool:
        raise ZeroDivisionError("compared")


class Calls:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other) -> bool:
        print("  ", self.name, "== ...")
        return False


class Base(Exception):
    def __eq__(self, other) -> bool:
        return other == 7


class Derived(Base):
    pass


class Plain:
    pass


class OnlyInts:
    def __eq__(self, other: int) -> bool:
        return other == 3


@dataclass
class D:
    x: int


class N(NamedTuple):
    x: int
    y: int


# the item's __eq__(x)
print(2 in (1, AlwaysEq()), 2 not in (1, AlwaysEq()))
print(2 in (1, NeverEq()), "s" in ("t", AlwaysEq()))
# x's __eq__(item), where the item's class has none
print(AlwaysEq() in (1, 2), AlwaysEq() in (1,), NeverEq() in (1, "a"))
print(OnlyInts() in ("a", 3), OnlyInts() in ("a", 4), 3 in (OnlyInts(),), 4 in (OnlyInts(),))
# order, and the first equal item ends the search
print(1 in (1, StopCompares()))
try:
    print(1 in (StopCompares(), 1))
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
print(5 in (Calls("a"), Calls("b"), 5, Calls("c")))
# an inherited __eq__ (of an exception class), and an object or None of a class without one
print(7 in (Derived(),), 8 in (Derived(),), 7 in (Base(), 1), 8 in (Base(), 1))
print(1 in (Plain(), 2), Plain() in (1, 2))
p = Plain()
print(p in (1, p))
maybe: AlwaysEq | None = None
print(1 in (maybe, 2), 2 in (maybe, 2))
maybe = AlwaysEq()
print(1 in (maybe, 2))
# a dataclass's and a NamedTuple's; a dataclass's __eq__ declines an object of another class,
# whose own __eq__ then decides
print(1 in (D(1), 2), D(1) in (1, D(1)), 1 in (N(1, 2), 3), 3 in (N(1, 2), 3))
print(AlwaysEq() in (D(1),), NeverEq() in (D(1),), D(1) in (AlwaysEq(),), D(2) in (NeverEq(), D(2)))
print(AlwaysEq() in (N(1, 2),), N(1, 2) in (AlwaysEq(),))
