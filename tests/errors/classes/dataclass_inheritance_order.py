# error: non-default argument 'y' follows default argument 'x'
from dataclasses import dataclass


@dataclass
class Base:
    x: int = 0


@dataclass
class Derived(Base):
    y: int


print(Derived(1, 2))
