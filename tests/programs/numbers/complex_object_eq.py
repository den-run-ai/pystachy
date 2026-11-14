# == and != of a complex number and an object of another class: complex's __eq__ declines it, as
# CPython's returns NotImplemented, so the object's own __eq__ or __ne__ answers, else identity
class Yes:
    def __eq__(self, other: object) -> bool:
        return True


class Never:
    def __ne__(self, other: object) -> bool:
        return False


class Plain:
    pass


z = 1 + 2j
y = Yes()
p = Plain()
print(z == y, y == z, z != y, y != z)
print(z != Never(), z == p, p == z, z != p, p != z)
