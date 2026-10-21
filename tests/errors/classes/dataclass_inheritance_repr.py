# error: repr=False in a dataclass whose base's __repr__ is the one @dataclass writes is not supported (CPython's shows the object's class, Derived)
from dataclasses import dataclass


@dataclass
class Base:
    x: int


@dataclass(repr=False)
class Derived(Base):
    y: int = 0


print(Derived(1))
