# An imported class's inferred getters, read and overridden in another module.
from property_inferred_support.shapes import Shape

s = Shape(6)
print(s.area, s.name)


class Cube(Shape):
    @property
    def area(self):
        return 6 * self.side * self.side


shapes: list[Shape] = [s, Cube(2)]
print([x.area for x in shapes], [x.name for x in shapes])
