from typing import Final
class C:
    A: Final = 3
    L: Final = [1]
    def __init__(self) -> None:
        self.x: Final = 1
C.A = 4
c = C()
c.x = 2
C.L.append(2)
print(C.A, c.x, C.L)
