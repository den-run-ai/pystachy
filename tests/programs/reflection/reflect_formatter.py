# string.Formatter().format() of a constant template whose fields read attributes (#486): the base
# Formatter formats as str.format() does, so its attribute fields ({0.x}) read the attributes the
# template names; a loop over a constant list of templates unrolls, one constant template each
import string


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


print(string.Formatter().format("{0.x},{0.y}", Point(1, 2)))
templates: list[str] = ["{0.x}", "{0.y}", "{0.x}-{0.y}", "{1}={0.y}"]
for t in templates:
    print(string.Formatter().format(t, Point(1, 2), "b"))
print(string.Formatter().format("{0.x!r:>4}|{1.y:03d}", Point(3, 4), Point(5, 6)))
