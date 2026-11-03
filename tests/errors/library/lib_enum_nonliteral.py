# error: enum member C.A is not supported: the compiler makes an enum class's members from literal values
# CPython calls f() as the class body runs (printing C.A)
from enum import Enum


def f() -> int:
    return 1


class C(Enum):
    A = f()


print(C.A)
