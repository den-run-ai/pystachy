from typing import final
import typing
@final
def f() -> int:
    return 1
class C:
    @final
    def m(self) -> int:
        return 2
    @typing.final
    @staticmethod
    def s() -> int:
        return 3
    @classmethod
    @final
    def c(cls) -> int:
        return 4
    @final
    @property
    def p(self) -> int:
        return 5
print(f(), C().m(), C.s(), C.c(), C().p)
