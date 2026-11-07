# pystachy: dynamic-any
from typing import Any


class C:
    __class__ = "pretend"


class Base:
    pass


class Child(Base):
    __class__ = "subclass"


def show(value: Base) -> None:
    print(value.__class__)


c = C()
print(c.__class__)
o: Any = c
print(o.__class__)
print(getattr(o, "__class__"))
print(c.__class__ == "pretend", o.__class__ == "pretend")
print(type(o) is C, C.__class__ is type)
plain: Any = 3
print(plain.__class__ is int, type(plain) is int)
show(Base())
show(Child())
