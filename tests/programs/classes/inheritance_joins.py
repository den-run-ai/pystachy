# Objects of two classes of one hierarchy where a value is one or the other take the type of
# their nearest common base: an if-else's arms, or's and and's operands, and the items of list,
# dict and set displays and comprehensions; calls then dispatch on each object's own class
class Shape:
    def area(self) -> float:
        return 0.0

    def name(self) -> str:
        return "shape"


class Circle(Shape):
    def __init__(self, r: float) -> None:
        self.r = r

    def area(self) -> float:
        return 3.0 * self.r * self.r

    def name(self) -> str:
        return "circle"


class Square(Shape):
    def __init__(self, s: float) -> None:
        self.s = s

    def area(self) -> float:
        return self.s * self.s

    def name(self) -> str:
        return "square"


class Polygon(Shape):
    def sides(self) -> int:
        return 0


class Triangle(Polygon):
    def sides(self) -> int:
        return 3


class Quad(Polygon):
    def sides(self) -> int:
        return 4


def pick(flag: int) -> Shape:
    return Circle(1.0) if flag else Square(2.0)


def describe(s: Shape) -> str:
    return f"{s.name()} {s.area()}"


def main() -> None:
    for flag in range(2):
        x = Circle(1.0) if flag else Square(2.0)
        print("if-else", x.name(), x.area())
        y: Shape = Square(3.0) if flag else Circle(2.0)
        print("annotated", y.name(), y.area())
        print("returned", pick(flag).name())
        print("argument", describe(Circle(0.5) if flag else Square(0.5)))
        z = Circle(1.0) if flag else Shape()
        print("base second", z.name())
        p = Triangle() if flag else Quad()
        print("nearest base", p.sides(), p.name())
        q = Triangle() if flag else Circle(2.0)
        print("farther base", q.name())
    c = Circle(1.0)
    s = Square(2.0)
    first = c or s
    print("or", first.name(), first is c)
    second = c and s
    print("and", second.name(), second is s)
    shapes = [c, s, Circle(2.0), Triangle()]
    shapes.append(Square(1.0))
    print("list", [t.name() for t in shapes], sum(t.area() for t in shapes))
    print("list identity", shapes[0] is c, shapes[1] is s)
    mixed = [Circle(1.0), Shape()]
    print("subclass first", [t.name() for t in mixed])
    polys = [Triangle(), Quad()]
    print("polygons", [t.sides() for t in polys])
    named = {"c": c, "s": s}
    named["t"] = Triangle()
    print("dict", sorted((k, v.name()) for k, v in named.items()))
    group = {c, s}
    print("set", sorted(t.name() for t in group), c in group, Square(2.0) in group)
    made = [Circle(float(i)) if i % 2 else Square(float(i)) for i in range(4)]
    print("comprehension", [t.name() for t in made], sum(t.area() for t in made))
    for t in made:
        if isinstance(t, Circle):
            print("narrowed", t.r)


main()
