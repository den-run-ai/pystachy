from typing import Generic, TypeVar

T = TypeVar("T")


class Base:
    def __init__(self, x):
        self.x = x

    @classmethod
    def make(cls, x: int):
        return cls(x)


class Sub(Base):
    def __init__(self, x: str) -> None:
        super().__init__(x)
        self.extra = x + x


class Child(Sub):
    pass


class Grand(Child):
    def __init__(self, x: str) -> None:
        super().__init__(x + x)
        self.tail = x


class Box(Generic[T]):
    def __init__(self, x: T):
        self.x = x

    @classmethod
    def make(cls, x: str):
        return cls(x)


class IntBox(Box[int]):
    pass


c = Child("a").make(1)
g = Grand("b").make(2)
i = IntBox(3).make("z")
print(type(c).__name__, c.x, c.extra, isinstance(c, Child), isinstance(c, Sub))
print(type(g).__name__, g.x, g.extra, g.tail, isinstance(g, Grand), isinstance(g, Sub))
print(type(i).__name__, i.x, isinstance(i, IntBox), isinstance(i, Box))
