from typing import Final
class C:
    def __init__(self) -> None:
        self.v = 4
def f() -> int:
    return 5
X: Final = C()
Y: Final = f()
Z: Final = len("abc")
print(X.v, Y, Z)
