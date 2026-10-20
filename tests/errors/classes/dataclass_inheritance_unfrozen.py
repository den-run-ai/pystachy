# error: cannot inherit frozen dataclass from a non-frozen one
from dataclasses import dataclass


@dataclass
class Base:
    x: int


@dataclass(frozen=True)
class Derived(Base):
    y: int = 0


print(Derived(1))
