# error: inheritance from a dataclass or NamedTuple is not supported
from dataclasses import dataclass


@dataclass
class Base:
    n: int


class Child(Base):
    pass


print(Child(1).n)
