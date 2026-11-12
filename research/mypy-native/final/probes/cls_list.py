from typing import Final
class C:
    FLAGS: Final = ["a", "b"]
    S: Final = {1, 2}
    T: Final = (1, "a")
    D: Final = {"k": 1}
print(C.FLAGS, sorted(C.S), C.T, C.D, C().FLAGS)
