# error: name 'make' is not defined (CPython reads a default_factory when it creates the class
from dataclasses import dataclass, field


@dataclass
class A:
    xs: list[int] = field(default_factory=make)


def make() -> list[int]:
    return [1]


print(A())
