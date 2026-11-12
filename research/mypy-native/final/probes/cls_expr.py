from typing import Final
class C:
    A: Final = 1 << 3
    B: Final = "a" + "b"
    C: Final = len("abc")
    D: Final = A + 1
print(C.A, C.B, C.C, C.D)
