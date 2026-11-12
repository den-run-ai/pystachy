from typing import Final
def make() -> int:
    class C:
        A: Final = 3
        L: Final = [1, 2]
    return C.A + len(C.L)
print(make())
