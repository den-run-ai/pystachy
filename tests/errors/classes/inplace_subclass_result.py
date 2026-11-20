# error: inplace_subclass_result.py:18: error: += on Base calls the in-place method of the object's class where it has one, whose results (int, Base) have no common type; give them one
# x += y through a Base, whose subclass's __iadd__ returns an int where Base's __add__ returns a
# Base: CPython rebinds x to either, which no variable of one type holds (#1538)
class Base:
    def __init__(self, n: int):
        self.n = n

    def __add__(self, other: int) -> "Base":
        return Base(self.n + other)


class Sub(Base):
    def __iadd__(self, other: int) -> int:
        return self.n + other


def run(x: Base) -> None:
    x += 2
    print(x)


run(Sub(1))
