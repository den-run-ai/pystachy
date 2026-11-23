# A class attribute that only an ordinary base binds, read through objects of class templates under
# it (#962) beside an ordinary subclass that binds it again: Circle's objects read Shape's, Ring's
# Mid's, Dot's (a member of Ring) its own, in a method of Shape and through a list of Shape.
class Shape:
    sides = 0

    def label(self) -> str:
        return str(self.sides)


class Rect(Shape):
    sides = 4

    def __init__(self, w: int) -> None:
        self.w = w


class Circle(Shape):
    def __init__(self, r):
        self.r = r


class Mid(Shape):
    sides = 3


class Ring(Mid):
    def __init__(self, r):
        self.r = r


class Dot(Ring):
    sides = 1


xs: list[Shape] = [Rect(1), Circle(1), Circle("s"), Shape(), Mid(), Ring(2), Ring("r"), Dot(2)]
for x in xs:
    print(x.label(), x.sides)
print(Circle(1).label(), Shape().label(), Circle(2).sides, Ring(1).sides, Dot("d").sides, Dot("d").label())
