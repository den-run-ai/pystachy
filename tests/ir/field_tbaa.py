# fieldtbaa (field_tbaa.tbaa): the loads and stores of an object's fields carry the TBAA tag of the
# class whose struct lays the field out. Labeled's struct begins with Point's, so its x and y are
# tagged as Point's, whichever class the reference names; its own n is Labeled's, at the offset
# after Point's members. Tally's count may be read before __init__ assigns it: its "is assigned"
# flag, at the end of its struct, is tagged too.
class Point:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


class Labeled(Point):
    def __init__(self, x: float, y: float, n: int) -> None:
        super().__init__(x, y)
        self.n = n


class Tally:
    def __init__(self, start: bool) -> None:
        if start:
            self.count = 0


def shift(p: Point, q: Labeled) -> float:
    p.x = q.y
    q.n = 1
    return p.y + q.x


def bump(t: Tally) -> int:
    t.count = t.count + 1
    return t.count


print(shift(Point(1.0, 2.0), Labeled(3.0, 4.0, 5)))
print(bump(Tally(True)))
