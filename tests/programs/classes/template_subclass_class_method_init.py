# An inherited factory may have an untaken call whose arguments do not fit the subclass
# constructor. That call would raise TypeError; the other branch keeps the subclass binding.
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
