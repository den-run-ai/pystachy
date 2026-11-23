# A method that returns one of two enum classes held in class attributes, which no one type
# holds, compiles where each call's literal argument chooses which (a call without a literal is
# rejected: tests/errors/library/lib_enum_class_attr_join.py)
from enum import Enum


class A(Enum):
    LOW = 1


class B(Enum):
    LOW = 2


class Registry:
    first = A
    second = B

    def choose(self, flag: bool):
        if flag:
            return self.first
        return self.second


r = Registry()
print(r.choose(True).LOW, r.choose(False).LOW, r.choose(flag=True).LOW.value)
print([m.name for m in r.choose(False)], r.choose(True) is A, r.choose(False) is B)
