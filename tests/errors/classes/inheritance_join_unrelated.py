# error: inheritance_join_unrelated.py:19: error: expected Circle, got Point
# classes with no common base have no type that holds an object of either (annotate it Circle | Point)
class Shape:
    def area(self) -> float:
        return 0.0


class Circle(Shape):
    def area(self) -> float:
        return 3.0


class Point:
    def area(self) -> float:
        return 0.0


def pick(flag: int):
    x = Circle() if flag else Point()
    return x.area()


print(pick(1))
