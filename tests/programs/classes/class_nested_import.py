# Classes nested in a class body of another module, read through the module and through the
# imported class: their objects, members, names and module, and an exception class's.
import nested_shapes
from nested_shapes import Shape


s = Shape(Shape.Kind.SQUARE, 3)
print(s.kind, repr(s.kind), s.size, nested_shapes.Shape.Size(4), nested_shapes.Shape.Kind(1), Shape.Kind.ROUND + 1)
print(Shape.Size.__qualname__, Shape.Size.__module__, Shape.Size, type(s.size).__name__, type(s.size).__module__)
try:
    raise nested_shapes.Shape.Bad("no")
except Shape.Bad as e:
    print(type(e).__name__, type(e).__qualname__, type(e).__module__, repr(e), type(e))
