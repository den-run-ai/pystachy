# error: expected float, got int (write a float literal like 1.0, or use float())
# A method that subclasses override keeps one typed interface: no int for its float (#711)
class Shape:
    def scaled(self, k: float) -> float:
        return k


class Square(Shape):
    def scaled(self, k: float) -> float:
        return k * 4


def total(s: Shape) -> float:
    return s.scaled(2)


print(total(Square()))
