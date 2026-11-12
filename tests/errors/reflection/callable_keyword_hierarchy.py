# error: keyword calls through Callable do not support methods in a class hierarchy
from typing import Callable


class Parent:
    def f(self, x: int) -> int:
        return x


class Child(Parent):
    def f(self, y: int) -> int:
        return y + 1


obj: Parent = Child()
fn: Callable[[int], int] = obj.f
print(fn(x=2))
