# Inferred getters in class hierarchies: overrides dispatch on the object's class, also
# where a base's getter only raises, returns None or is annotated, and through super().
class Shape:
    def __init__(self, side: float) -> None:
        self.side = side

    @property
    def area(self):
        return 0.0

    @property
    def label(self):
        return "shape"

    @property
    def kind(self):
        raise NotImplementedError("kind of " + self.label)

    @property
    def parent(self):
        return None

    @property
    def corners(self) -> int:
        return 0

    @property
    def weight(self):
        return 1.5


class Square(Shape):
    @property
    def area(self):
        return self.side * self.side

    @property
    def kind(self):
        return "square"

    @property
    def corners(self):
        return 4

    @property
    def weight(self) -> float:
        return 2.5


class Cube(Square):
    def __init__(self, side: float, base: Shape) -> None:
        super().__init__(side)
        self.base = base

    @property
    def label(self):
        return "cube of " + super().label

    @property
    def area(self):
        return 6 * super().area

    @property
    def parent(self):
        return self.base

    @property
    def corners(self):
        return 2 * super().corners


def show(s: Shape) -> None:
    try:
        k = s.kind
    except NotImplementedError as e:
        k = "error: " + str(e)
    p = s.parent
    print(s.area, s.label, k, s.corners, s.weight, "-" if p is None else p.label)


sq = Square(2.0)
shapes: list[Shape] = [Shape(1.0), sq, Cube(3.0, sq)]
for s in shapes:
    show(s)
print(sq.area + Cube(1.0, sq).area, Cube(1.0, sq).corners + sq.corners)


class Cat:
    @property
    def sound(self):
        return "meow"

    @property
    def legs(self):
        return 4


class Bird:
    @property
    def sound(self):
        return "tweet"

    @property
    def legs(self):
        return 2


def describe(a: Cat | Bird) -> str:
    return f"{a.sound} {a.legs}"


def maybe(a: Cat | None) -> str:
    if a is None:
        return "none"
    return a.sound


pets: list[Cat | Bird] = [Cat(), Bird()]
print(describe(Cat()), describe(Bird()), maybe(None), maybe(Cat()), sum(p.legs for p in pets))


class Node:
    def __init__(self, up: "Node | None") -> None:
        self.up = up

    @property
    def depth(self):
        if self.up is None:
            return 0
        return self.up.depth + 1


print(Node(Node(Node(None))).depth)
