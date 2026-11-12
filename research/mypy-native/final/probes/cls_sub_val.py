from typing import Final
class C:
    A: Final[int] = 3
    L: Final[list[str]] = ["x"]
print(C.A, C.L, C().A)
