from typing import Callable


def twice(x: int) -> int:
    return x * 2


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    @property
    def value(self) -> int:
        return self.n

    @property
    def callback(self) -> Callable[[int], int]:
        return twice

    def describe(self) -> str:
        return f"value={self.value}"


class Child(Base):
    @property
    def value(self) -> int:
        return super().value + 10

    @property
    def callback(self) -> Callable[[int], int]:
        return super().callback

    def call_base(self, n: int) -> int:
        return super().callback(n)


class Grandchild(Child):
    pass


def show(b: Base) -> None:
    print(b.value, b.describe(), b.callback(4))


show(Base(1))
show(Child(2))
show(Grandchild(3))
print(Grandchild(5).call_base(6))
