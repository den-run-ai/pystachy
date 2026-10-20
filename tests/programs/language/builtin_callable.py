# callable(): functions, lambdas, closures, bound methods, builtins and Callables are
# callable; objects are where their class defines __call__ (and they are not None); other
# values are not. A guard that exits where a parameter is not callable leaves its class's
# isinstance() tests to its type, as for an object known not to be None
from typing import Callable


class Adder:
    def __init__(self, k: int) -> None:
        self.k = k

    def __call__(self, x: int) -> int:
        return x + self.k

    def get(self) -> int:
        return self.k


class Plain:
    pass


def inc(x: int) -> int:
    return x + 1


def make(n: int):
    def inner() -> int:
        return n

    return inner


f: Callable[[int], int] = inc
g: Callable[[int], int] | None = None
a = Adder(2)
none_adder: Adder | None = None
print(callable(inc), callable(lambda: 0), callable(make(3)), callable(a.get), callable(len), callable(str.upper))
print(callable(f), callable(g), callable(a), callable(none_adder), callable(Plain()))
print(callable(0), callable("inc"), callable(None), callable([inc]), callable((1,)), callable({"a": inc}))
g = inc
print(callable(g))


def describe(x):
    if not callable(x):
        raise TypeError("not callable")
    if isinstance(x, Adder):
        return "adder " + str(x(1))
    return "function " + str(x(1))


for arg in [a, Adder(5)]:
    print(describe(arg))
print(describe(inc))
try:
    describe(none_adder)
except TypeError as e:
    print("TypeError:", e)
try:
    describe(7)
except TypeError as e:
    print("TypeError:", e)
