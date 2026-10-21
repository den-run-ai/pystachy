# error: non-default argument 'y' follows default argument 'x'
from dataclasses import dataclass, field


@dataclass
class Base:
    x: int = 0
    y: int = 1


@dataclass
class Derived(Base):
    y: int = field(compare=False)  # (declared again without a default, in its place)


print(Derived(1, 2))
