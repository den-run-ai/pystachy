# error: field 'x' of 'Base' declared again in 'Derived' with another type (not supported)
from dataclasses import dataclass


@dataclass
class Base:
    x: int


@dataclass
class Derived(Base):
    x: float = 0.5


print(Derived())
