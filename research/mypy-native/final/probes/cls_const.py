from typing import Final
class C:
    A: Final = 3
    B: Final = "b"
    N: Final = -1
    F: Final = 1.5
    T: Final = True
print(C.A, C.B, C.N, C.F, C.T, C().A)
