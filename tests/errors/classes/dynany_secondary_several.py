# error: an object of class Both, with several secondary bases, as an Any value is not supported
# pystachy: dynamic-any
# An Any value's isinstance() tests one secondary base of its class (pys_dyn_role_isa): it would
# answer False for Second, where CPython answers True
from typing import Any


class Base:
    pass


class First:
    def first(self) -> int:
        return 1


class Second:
    def second(self) -> int:
        return 2


class Both(Base, First, Second):
    pass


x: Any = Both()
print(isinstance(x, Second))
