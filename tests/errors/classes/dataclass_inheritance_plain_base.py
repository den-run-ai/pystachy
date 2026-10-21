# error: a @dataclass class whose base is not a dataclass is not supported
from dataclasses import dataclass


class Base:
    def __init__(self) -> None:
        self.x = 1


@dataclass
class Derived(Base):
    y: int = 0


print(Derived())
