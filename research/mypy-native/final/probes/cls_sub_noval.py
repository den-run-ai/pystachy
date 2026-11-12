from typing import Final
class C:
    x: Final[int]
    def __init__(self, x: int) -> None:
        self.x = x
print(C(4).x)
