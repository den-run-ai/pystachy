from typing import Final
BASE = 7
class Other:
    def __init__(self) -> None:
        self.v = 1
class C:
    A: Final = BASE
    B: Final = Other
    O: Final = Other()
print(C.A, C.B().v, C.O.v)
