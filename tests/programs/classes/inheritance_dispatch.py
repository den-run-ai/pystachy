# A base annotation must preserve the receiver's concrete class. Calls made inside an inherited
# method remain virtual, while an explicit Base.method(obj) selects that implementation only.
from typing import Callable


class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def value(self, extra: int = 2) -> int:
        return self.n + extra

    def twice(self, extra: int = 3) -> int:
        return self.value(extra) * 2

    def callback(self) -> Callable[[int], int]:
        return self.value


class Scaled(Base):
    def value(self, extra: int = 5) -> int:
        return self.n * 10 + extra


class More(Scaled):
    pass


def report(obj: Base) -> None:
    print(obj.value(), obj.twice(), obj.twice(4), obj.callback()(6))
    bound: Callable[[int], int] = obj.value
    print(bound(7), Base.value(obj, 8), Base.twice(obj, 9))


a = Base(1)
b = Scaled(2)
c = More(3)
report(a)
report(b)
report(c)
base: Base = c
print(base.value(), base.twice(), Base.value(c), Base.twice(c))
items: list[Base] = [a, b, c]
print([x.value(1) for x in items])
print([x.twice(2) for x in items])
callbacks: list[Callable[[int], int]] = [x.value for x in items]
print([f(3) for f in callbacks])
