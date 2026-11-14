# A subclass's method that tests its operand, then calls the base class's method, which returns
# NotImplemented for another class: the operand's class is known in the call.
class Point:
    def __init__(self, x: int) -> None:
        self.x = x

    def __eq__(self, other):
        print("Point.__eq__")
        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x

    def __lt__(self, other):
        if not isinstance(other, Point):
            return NotImplemented
        return self.x < other.x


class Point3(Point):
    def __init__(self, x: int, z: int) -> None:
        super().__init__(x)
        self.z = z

    def __eq__(self, other):
        print("Point3.__eq__")
        if not isinstance(other, Point3):
            return NotImplemented
        return super().__eq__(other) and self.z == other.z


ps: list[Point] = [Point(1), Point3(1, 2), Point3(1, 2), Point3(1, 3)]
for a in ps:
    for b in ps:
        print(a == b, a != b)
print(ps[1] == 3, ps[1] == None, ps[0] < ps[3])
