# Documented deviation (docs/dynamic-any.md): in a module that compiles typing.Any as dynamic
# values, a comparison method whose parameter is annotated with a class is compiled for objects of
# the class, and does not run with a value of another type that an Any value brings it: the
# comparison is identity's, or the ordering's TypeError, where CPython runs the method (here it
# would print "__eq__ ran" twice, True True, and the TypeError that __lt__ raises).
# pystachy: dynamic-any
from typing import Any


class Loose:
    def __eq__(self, other: "Loose") -> bool:
        print("__eq__ ran")
        return True

    def __lt__(self, other: "Loose") -> bool:
        raise TypeError("Loose orders only Loose objects")


x: Any = Loose()
one: Any = 1
print(x == one, one == x)
try:
    print(one > x)
except TypeError as err:
    print("TypeError:", err)
