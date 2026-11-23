# A class method of a class template that calls cls(...) on a path the program does not take,
# inherited by a class whose own __init__ takes another argument. The class's own copy of the
# method would call that __init__ with too few arguments and not compile, so the program is
# compiled without such copies, as before they were made (#1744), and runs as CPython runs it
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
    def __init__(self, size, color):
        super().__init__(size)
        self.color = color


sq = Square(2, "red")
print(sq.describe(False))
