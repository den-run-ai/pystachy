from typing import Final
class B:
    L: Final = ["a"]
    K: Final = 2
class D(B):
    M: Final = ("x",)
d = D()
print(D.L, d.L, D.K, d.K, D.M, d.M)
