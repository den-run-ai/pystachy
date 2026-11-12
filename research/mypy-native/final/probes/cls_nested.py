from typing import Final
class Outer:
    class Inner:
        A: Final = 3
        L: Final = [1, 2]
print(Outer.Inner.A, Outer.Inner.L)
