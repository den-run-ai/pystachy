# error: cannot inherit non-frozen dataclass from a frozen one
from dataclasses import dataclass


@dataclass(frozen=True)
class Base:
    x: int


@dataclass
class Derived(Base):
    y: int = 0


print(Derived(1))
