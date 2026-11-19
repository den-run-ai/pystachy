# x op= y of an int | Base union whose object's class alone defines the in-place method (#1538):
# CPython calls that method, which changes the object; a Base object takes Base.__add__, and an
# int its own addition
import sys


class Base:
    def __init__(self, n: int):
        self.n = n

    def __add__(self, other: int) -> "Base":
        return Base(self.n + other)

    def __radd__(self, other: int) -> "Base":
        return Base(self.n + other)


class Sub(Base):
    def __iadd__(self, other: int) -> "Base":
        self.n += 100 * other
        return self


def run(k: int) -> None:
    x: int | Base = Sub(1) if k == 0 else Base(1) if k == 1 else 7
    y = x
    x += 2
    if isinstance(x, Base) and isinstance(y, Base):
        print(x.n, y.n, x is y)
    else:
        print(x, y)


for k in range(3):
    run(k + len(sys.argv) - 1)
