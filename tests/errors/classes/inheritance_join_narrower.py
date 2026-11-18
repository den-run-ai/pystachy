# error: inheritance_join_narrower.py:19: error: expected Circle, got Square
# the arms' common base is no Circle: the expected type stays what the arms are converted to
class Shape:
    def area(self) -> float:
        return 0.0


class Circle(Shape):
    def area(self) -> float:
        return 3.0


class Square(Shape):
    def area(self) -> float:
        return 4.0


def pick(flag: int) -> float:
    x: Circle = Circle() if flag else Square()
    return x.area()


print(pick(1))
