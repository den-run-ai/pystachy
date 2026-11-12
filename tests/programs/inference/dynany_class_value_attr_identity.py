# pystachy: dynamic-any
# A numeric class attribute read, or returned by a class method, through a class object keeps
# its identity as an Any value, as a read through the class does.
from typing import Any


class A:
    x = int("1000")
    y = float("2.5")

    @classmethod
    def get(cls) -> int:
        return cls.x


class B(A):
    x = int("2000")


def check(k: type[A]) -> None:
    a: Any = k.x
    b: Any = k.x
    c: Any = k.get()
    d: Any = k.y
    e: Any = k.y
    print(a is b, a == b, a is c, d is e)


check(A)
check(B)
