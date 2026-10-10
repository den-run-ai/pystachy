from typing import override
class B:
    def f(self) -> int:
        return 0
class C(B):
    @override
    def f(self) -> int:
        return 1
print(C().f())
