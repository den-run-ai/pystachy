# A class template under an ordinary class in an imported module (#962): compiled where the program
# uses it, its hierarchy requested then, as an imported subclass of a class template is.
class Shape:
    def __init__(self) -> None:
        self.sides = 0

    def describe(self) -> str:
        return self.kind() + " with " + str(self.sides) + " sides"

    def kind(self) -> str:
        return "shape"


class Poly(Shape):
    def __init__(self, sides, label):
        super().__init__()
        self.sides = sides
        self.label = label

    def kind(self) -> str:
        return "poly " + str(self.label)


class Unused(Shape):
    # (a class template too, which the program does not use: left out)
    def __init__(self, size):
        super().__init__()
        self.size = size
