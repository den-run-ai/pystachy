# Quoted annotations that name what only an `if TYPE_CHECKING:` import binds: the program's own
# class where it loads that module anyway, else an annotation that types nothing.
from tcmods.helpers import describe, label, labels
from tcmods.lazy import Box, widest
from tcmods.shapes import Shape


class Named:
    def __init__(self, name: str) -> None:
        self.name = name


a = Shape("a", 2, 3)
b = Shape("b", 5, 1)
print(a.area(), a.text(), describe(a, b))
c = a.twice()
print(c is a, a.w, a.h, c.area())
print(widest(a, b).name, widest(b, a).name, Box(b).area())
print(label(Named("n")), label(a), labels([Named("x"), Named("y")]))
