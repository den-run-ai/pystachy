# pystachy: dynamic-any
# Comparison methods whose body does not compile for an Any operand, several of one class (Bag),
# of several classes (Bag, Ver) and of a class template's specializations (Box of an int and of a
# str): the compiler declines them all in one more pass (#801), and each runs with objects of its
# class, as in a module that does not opt in. Money's method, compiled after them, takes an Any
# operand and runs with a value of another type.
from typing import Any


class Bag:
    def __init__(self, n: int) -> None:
        self.items = [1, n]

    def __eq__(self, other):
        return self.items == other.items

    def __lt__(self, other):
        return self.items < other.items

    def __le__(self, other):
        return self.items <= other.items


class Ver:
    def __init__(self, parts: list[int]) -> None:
        self.parts = parts

    def __gt__(self, other):
        return self.parts > other.parts


class Box:
    def __init__(self, v):
        self.items = [v]

    def __eq__(self, other):
        return self.items == other.items


class Money:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other):
        if isinstance(other, int):
            return self.v == other
        return False


b1: Any = Bag(1)
b2: Any = Bag(2)
print(b1 == b1, b1 == b2, b1 < b2, b2 <= b1, b1 != b2)
v1: Any = Ver([1, 2])
v2: Any = Ver([1, 3])
print(v2 > v1, v1 > v2)
i1: Any = Box(1)
i2: Any = Box(1)
s1: Any = Box("a")
s2: Any = Box("b")
print(i1 == i2, s1 == s2, s1 == s1)
m: Any = Money(5)
five: Any = 5
print(m == five, five == m, m == "x", m != five)
