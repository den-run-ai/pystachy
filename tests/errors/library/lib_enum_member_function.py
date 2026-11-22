# error: enum member C.f is not supported: its value is a function (@member)
# CPython makes the function a member's value (printing C.f)
from enum import Enum, member


class C(Enum):
    A = 1

    @member
    def f(self) -> int:
        return 2


print(C.f)
