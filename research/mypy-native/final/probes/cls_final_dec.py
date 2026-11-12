from typing import Final, final
@final
class C:
    A: Final = 3
    L: Final = [1, 2]
    @final
    def m(self) -> int:
        return self.A
print(C.A, C.L, C().m())
