# getattr(o, "name") with a str literal name reads o.name: fields, class attributes,
# properties, bound methods (also called directly) and builtin types' methods, o evaluated
# once, then the attribute; None raises CPython's AttributeError
class Point:
    unit = "cm"

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    @property
    def norm1(self) -> int:
        return abs(self.x) + abs(self.y)

    def moved(self, dx: int, dy: int = 0) -> "Point":
        return Point(self.x + dx, self.y + dy)


def make(x: int) -> Point:
    print("make", x)
    return Point(x, -x)


p = Point(3, 4)
print(getattr(p, "x"), getattr(p, "unit"), getattr(p, "norm1"), getattr(make(2), "y"))
m = getattr(p, "moved")
print(m(1).x, getattr(p, "moved")(1, 2).y, getattr(make(5), "moved")(dx=1).x)
print(getattr("abc", "upper")(), getattr([3, 1, 2], "count")(1), getattr("a,b", "split")(","))
xs = [1]
getattr(xs, "append")(2)
print(xs, getattr({"k": 1}, "get")("k"))


def field(o):
    return getattr(o, "x")


print(field(p), field(Point(-1, 0)))
maybe: Point | None = None
try:
    print(getattr(maybe, "x"))
except AttributeError as e:
    print("AttributeError:", e)
