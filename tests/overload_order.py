# @overload stubs: several names' stubs interleaved before their implementations, stubs with
# constant defaults and ..., annotations Pystachy does not support in a stub (CPython evaluates
# them, so they name what is bound), a quoted later class, and overloaded methods.
from typing import overload


@overload
def f(x: int) -> int: ...
@overload
def g(x: bytes, n: int = 3) -> bytes: ...
@overload
def f(x: str, sep: str = ", ", count: int = ...) -> str: ...
def g(x: int, n: int = 3) -> int:
    return x * n
def f(x: int) -> int:
    return x + 1


class Box:
    @overload
    def put(self, v: "Later") -> "Box": ...
    @overload
    def put(self, v: frozenset[int]) -> "Box": ...
    def put(self, v: int) -> "Box":
        self.v = v
        return self

    def __init__(self) -> None:
        self.v = 0


class Later:
    pass


print(f(1), g(2), g(2, 4), Box().put(5).v)
