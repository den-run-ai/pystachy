class Style:
    def __init__(self, fmt):
        self.fmt = fmt

    @classmethod
    def make(cls, fmt: int):
        return cls(fmt)


class Sub(Style):
    pass


s = Sub(1).make(2)
print(type(s).__name__, s.fmt)
s = Style(3)
print(type(s).__name__, s.fmt)


class Shape:
    kind = "shape"

    def __init__(self, size):
        self.size = size

    @classmethod
    def describe(cls, verbose: bool) -> str:
        if verbose:
            return cls.kind + " " + str(cls(0).size)
        return cls.kind


class Square(Shape):
    kind = "square"

    def __init__(self, size, color):
        super().__init__(size)
        self.color = color


sq = Square(2, "red")
print(sq.describe(False))
try:
    print(sq.describe(True))
except TypeError as e:
    print(type(e).__name__, str(e))
