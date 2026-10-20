# error: inheritance from a dataclass is only supported by a @dataclass class
from dataclasses import dataclass


@dataclass
class Base:
    n: int


class Child(Base):
    pass


print(Child(1).n)
