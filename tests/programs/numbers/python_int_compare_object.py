# pystachy: python-int
# A promoting int and an object whose class defines no __eq__ are never equal, as CPython
# compares them by identity; a class's own __eq__ is asked, with the int on either side
class Plain:
    pass


class Big:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, int) and other > 2 ** 64


x = 2 ** 70
print(x == Plain(), Plain() == x, x != Plain(), Plain() != x)
print(x == Big(), Big() == x, Big() == 5, 5 != Big())
