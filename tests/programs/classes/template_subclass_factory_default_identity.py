# pystachy: dynamic-any
# pystachy: python-int
from typing import Any


class Base:
    def __init__(self, x):
        self.x = x

    @classmethod
    def make(cls, x: int):
        return cls(x)


class Sub(Base):
    extra: str = "class default"

    def __init__(self, x: str) -> None:
        before: Any = self.extra
        print(before is Sub.extra)
        Sub.reset(" ".join(["new", "default"]))
        after: Any = self.extra
        print(before, after, before is after, after is Sub.extra)
        super().__init__(x)
        self.extra = x + x

    @classmethod
    def reset(cls, value: str) -> None:
        cls.extra = value


original = Sub("a")
made = original.make(1000)
first: Any = made.extra
second: Any = made.extra
print(type(made).__name__, isinstance(made, Sub), made.x, first)
print(first is second, Sub.extra, original.extra)


class Fixed(Base):
    extra: str = "fixed default"

    def __init__(self, x: str) -> None:
        super().__init__(x)
        self.extra = x + x


fixed = Fixed("b").make(1500)
fixed_first: Any = fixed.extra
fixed_second: Any = fixed.extra
print(type(fixed).__name__, fixed.x, fixed_first, fixed_first is fixed_second)
print(Fixed.extra)
