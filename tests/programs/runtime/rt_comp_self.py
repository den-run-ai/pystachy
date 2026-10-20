from typing import Optional


class N:
    def __init__(self, v: int):
        self.v = v

    def vals(self, xs: list[Optional["N"]]) -> list[int]:
        return [self.v for self in xs]


print(N(0).vals([N(1), None]))
