# class C(object) is a class without bases where object is the builtin, as it is after
# from builtins import object (a module that binds object itself makes it inheritance)
from builtins import object


class Point(object):
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"


class Empty(object):
    pass


print(Point(1, 2), [Point(3, 4)], Point(5, 6).x + Point(7, 8).y)
