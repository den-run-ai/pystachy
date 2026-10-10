from typing import overload
class C:
    @overload
    def f(self, x: int) -> int: ...
    @overload
    def f(self, x: str) -> str: ...
    def f(self, x):
        return x
print(C().f(1))
