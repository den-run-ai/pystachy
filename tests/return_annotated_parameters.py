from typing import Callable

def double(x: int):
    return x * 2

def text(prefix: str, /, n: int = 2, *, suffix: str = "!"):
    return prefix * n + suffix

def optional(flag: bool):
    if flag:
        return None
    return "found"

class Value:
    def __init__(self, n: int):
        self.n = n

    def add(self, x: int):
        return self.n + x

    @staticmethod
    def scale(x: int, n: int = 2):
        return x * n

    @classmethod
    def make(cls, n: int):
        return cls(n)

print(double(3), double(5))
print(text("a"), text("b", 3, suffix="?"))
print(optional(False), optional(True))
value = Value.make(4)
print(value.add(3), value.scale(3), Value.scale(3, 4))
callback: Callable[[int], int] = double
method: Callable[[int], int] = value.add
print(callback(9), method(6))

def recursive(n: int):
    if n > 0:
        return recursive(n - 1)

print(recursive(3))

def first(n: int):
    return second(n)

def second(n: int):
    if n > 0:
        return first(n - 1)

print(first(3))

def known(n: int):
    if n == 0:
        return 1
    return known(n - 1) + 1

print(known(3))
