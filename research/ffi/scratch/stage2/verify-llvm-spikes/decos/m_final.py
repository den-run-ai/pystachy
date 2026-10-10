from typing import final
class C:
    @final
    def f(self) -> int:
        return 1
print(C().f())
