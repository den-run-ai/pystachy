# class objects of another module's classes: read through the module or imported by name, kept
# in that module's globals, and called here; a class of this module derives from one of them
import mods.classval_shapes
import mods.classval_shapes as shapes
from mods.classval_shapes import Shape, Square


class Local(mods.classval_shapes.Shape):
    def area(self) -> int:
        return 9


def area_of(kind: type[Shape]) -> int:
    return kind().area()


print(area_of(Square), area_of(shapes.Circle), area_of(Local), area_of(Shape))
print(Square, shapes.Circle, Local, Square.__module__, Local.__module__, shapes.pick(1).__name__)
print(shapes.pick(0) is Square, shapes.pick(1) is shapes.Circle, shapes.KINDS[0] is Square, shapes.early())
print(shapes.registry["circle"]().area(), sorted(shapes.registry), shapes.FIRST)
