# An enum __init__ defined before the members evaluates its defaults when its def runs.
from enum import Enum


def base() -> int:
    print("base called")
    return 40


class First(Enum):
    def __init__(self, n: int, extra: int = base() + 2, label: str = "p" + str(base())) -> None:
        self.n = n
        self.extra = extra
        self.label = label

    A = 1
    B = 2


for p in First:
    print(p.name, p.n, p.extra, p.label)
