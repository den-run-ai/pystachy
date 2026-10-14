# error: to Callable requires compatible signatures and annotated return types throughout its hierarchy
from typing import Callable


class Base:
    def value(self, n):
        return n


class Child(Base):
    def value(self, n):
        return n + 1


child = Child()
callback: Callable[[int], int] = child.value
print(callback(2))
