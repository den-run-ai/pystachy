# error: default_factory= is only supported as a function, a class or a lambda without parameters
from dataclasses import dataclass, field


def factories() -> list[int]:
    return [1]


@dataclass
class A:
    xs: list[int] = field(default_factory=[factories][0])
