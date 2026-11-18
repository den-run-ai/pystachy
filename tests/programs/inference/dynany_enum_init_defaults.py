# pystachy: dynamic-any
# An enum __init__'s numeric defaults in a module that opts in to dynamic Any.
from enum import Enum


class Planet(Enum):
    A = 1
    B = 2

    def __init__(self, n: int, extra: int = 7, ratio: float = 1.5, label: str = "x") -> None:
        self.n = n
        self.extra = extra
        self.ratio = ratio
        self.label = label


for p in Planet:
    print(p.name, p.n, p.extra, p.ratio, p.label)
