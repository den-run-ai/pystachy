# Subclasses of a class template override a method: a variable and a list of the base's
# specialization hold objects of each class, and a call through them dispatches on the
# object's class, also from the base's own methods (#962).
class Shape:
    def __init__(self, name, size):
        self.name = name
        self.size = size

    def area(self) -> int:
        return 0

    def describe(self) -> str:
        return self.name + ": " + str(self.area())


class Square(Shape):
    def area(self) -> int:
        return self.size * self.size


class Rect(Shape):
    def __init__(self, w: int, h: int) -> None:
        super().__init__("rect", w)
        self.h = h

    def area(self) -> int:
        return self.size * self.h


s = Shape("blob", 3)
print(s.describe())
s = Square("square", 4)
print(s.describe())
s = Rect(2, 5)
print(s.describe())

shapes = [Shape("blob", 1), Square("sq", 2), Rect(3, 4)]
for x in shapes:
    print(x.name, x.area(), x.describe())
total = 0
for x in shapes:
    total += x.area()
print(total)


def biggest(xs: list[Shape]) -> str:
    best = xs[0]
    for x in xs:
        if x.area() > best.area():
            best = x
    return best.describe()


print(biggest(shapes))
