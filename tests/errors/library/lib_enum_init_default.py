# error: enum class Planet's __init__(): the default value of parameter 'extra' is not supported where the members precede the def statement
from enum import Enum


def base() -> int:
    print("base called")
    return 40


class Planet(Enum):
    A = 1
    B = 2

    def __init__(self, n: int, extra: int = base() + 2, label: str = "p" + str(base())) -> None:
        self.n = n
        self.extra = extra
        self.label = label


for p in Planet:
    print(p.name, p.n, p.extra, p.label)
