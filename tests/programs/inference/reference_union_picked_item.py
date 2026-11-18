# An object that may be None enters a union's box through a choice between None and the box.
# The IR check (PYSTACHY_IRCHECK=1) must still see which member the box holds when a later
# isinstance() chain narrows an item picked from a tuple of objects of different classes.


class Circle:
    def __init__(self, radius: int) -> None:
        self.radius = radius

    def describe(self) -> str:
        return "circle " + str(self.radius)


class Square:
    def __init__(self, side: int) -> None:
        self.side = side

    def describe(self) -> str:
        return "square " + str(self.side)


class Label:
    def __init__(self, text: str) -> None:
        self.text = text


def describe(i: int) -> str:
    item = (Circle(1), Square(2), Label("three"))[i]
    if isinstance(item, Circle):
        return item.describe()
    if isinstance(item, Square):
        return item.describe() + "!"
    return item.text


def first(items: list[Circle], other: Square) -> Circle | Square:
    if len(items) > 0:
        return items[0]
    return other


def name(shape: Circle | Square) -> str:
    if isinstance(shape, Square):
        return shape.describe()
    return "a " + shape.describe()


for n in range(3):
    print(describe(n), describe(n - 3))
try:
    describe(3)
except IndexError as e:
    print("IndexError:", e)
print(name(first([Circle(4)], Square(5))), name(first([], Square(5))))
