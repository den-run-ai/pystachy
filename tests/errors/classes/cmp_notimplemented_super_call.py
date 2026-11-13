# error: Base.__eq__() returns NotImplemented for these operands, which only a comparison of objects (==, <, ...) reads: calling it directly is not supported
class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other):
        if not isinstance(other, Base):
            return NotImplemented
        return self.n == other.n


class Sub(Base):
    def __eq__(self, other):
        # (no test of other first: for an int, CPython's call returns NotImplemented)
        return super().__eq__(other)


xs: list[Base] = [Sub(1), Base(1)]
print(xs[0] == xs[1], xs[0] == 3)
