from __future__ import annotations
from typing import Final
X: Final = 3
Y: Final[list[int]] = [1]
class C:
    A: Final = 1
    B: Final = [1, 2]
print(X, Y, C.A, C.B)
