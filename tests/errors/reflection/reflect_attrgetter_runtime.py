# error: getattr() of a name only the run time knows is supported where its text is used
# attrgetter(name) with a name read at run time: its value as a sort key needs a type of its own (#487)
from operator import attrgetter


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


pts = [Point(3, 1), Point(1, 2)]
key = input()
print([(p.x, p.y) for p in sorted(pts, key=attrgetter(key))])
