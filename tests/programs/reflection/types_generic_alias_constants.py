# A class whose body binds __class_getitem__ = classmethod(GenericAlias) may be subscripted with
# constants in an annotation, evaluated or quoted, as CPython does not check that its arguments
# are types: Box[1], Box[...] and Box[int, ...] annotate an object of Box. A string argument is a
# forward reference, as elsewhere in an annotation (Box["Box"])
from types import GenericAlias


class Box:
    __class_getitem__ = classmethod(GenericAlias)

    def __init__(self, n: int) -> None:
        self.n = n


def double(b: Box[1]) -> Box["Box"]:
    return Box(b.n * 2)


a: Box[...] = Box(3)
b: Box[int, ...] = double(a)
c: Box[None, -1, 2.5, True] = double(b)
d: "Box[0, None]" = double(c)
print(a.n, b.n, c.n, d.n, isinstance(d, Box))
