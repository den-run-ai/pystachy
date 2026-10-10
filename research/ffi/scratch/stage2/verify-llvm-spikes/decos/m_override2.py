from typing import override
class C:
    @override
    def f(self) -> int:
        return 1
print(C().f())
