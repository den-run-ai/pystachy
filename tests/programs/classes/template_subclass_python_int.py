# pystachy: python-int
# In a module that opts in to promoting ints, a template hierarchy's root takes an int argument
# as a promoting int, also among *args: a literal's int and a parameter annotated int, which a
# subclass's super().__init__(...) passes, make one specialization, and so one hierarchy (#962).
class Shape:
    def __init__(self, name, size, *dims):
        self.name = name
        self.size = size
        self.dims = dims

    def area(self) -> int:
        return self.size * self.size


class Rect(Shape):
    def __init__(self, w: int, h: int) -> None:
        super().__init__("rect", w, w, h)

    def area(self) -> int:
        return self.dims[0] * self.dims[1]


class Square(Shape):
    pass


shapes = [Shape("blob", 3, 1, 2), Rect(2, 5), Square("sq", 4, 4, 4)]
for s in shapes:
    print(s.name, s.size, s.dims, s.area())
big = Rect(2 ** 40, 2 ** 40)
print(big.area(), big.dims[0] + 1)
s = Shape("big", 2 ** 70, 0, 0)
print(s.area())
s = Rect(3, 4)
print(s.area())
