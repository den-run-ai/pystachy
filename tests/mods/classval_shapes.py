# classes whose class objects another module uses (tests/programs/classes/class_value_modules.py)
def early() -> str:
    try:
        k = Circle
        return k.__name__
    except NameError as e:
        return "NameError: " + str(e)


class Shape:
    def area(self) -> int:
        return 0


class Square(Shape):
    def area(self) -> int:
        return 4


FIRST = early()


class Circle(Shape):
    def area(self) -> int:
        return 3


KINDS: list[type[Shape]] = [Square, Circle]
registry: dict[str, type[Shape]] = {"square": Square, "circle": Circle}


def pick(i: int) -> type[Shape]:
    return KINDS[i]
