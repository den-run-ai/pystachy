# In a module that opts in to dynamic Any, an ordinary class is a typed class object (type[C]),
# as in other modules (#7), and an Any value where one is stored: the class box that such a
# module made of it before. A call of a class object makes an object of its class, also of a
# class in a hierarchy whose constructor no other call compiled, which a call through Any
# cannot make.
# pystachy: dynamic-any
from typing import Any


class Shape:
    sides = 0

    def __init__(self, name: str) -> None:
        self.name = name

    def area(self) -> float:
        return 0.0


class Square(Shape):
    sides = 4

    def __init__(self, name: str) -> None:
        super().__init__(name + "!")

    def area(self) -> float:
        return 4.0


class Circle(Shape):
    def area(self) -> float:
        return 3.0


def make(kind: type[Shape], name: str) -> Shape:
    return kind(name)


def describe(kind: type[Shape]) -> str:
    return kind.__name__ + "/" + kind.__qualname__


kinds = [Square, Circle]
for k in kinds:
    s = make(k, "s")
    print(type(s).__name__, s.name, s.area(), type(s) is k, isinstance(s, k), issubclass(k, Shape))

chosen = Square
print(chosen("x").name, describe(chosen), chosen is Square, chosen == Circle)
print(chosen, [chosen], {"k": chosen}, str(chosen), repr(Circle))

# a class object stored as an Any value is its class box: the same object as the class
box: Any = Square
print(box is Square, box == Square, box is Circle, Circle != box, box.__name__)
registry: dict[Any, Any] = {}
registry[Square] = "square"
registry[int] = "int"
registry[type(Circle("c"))] = "circle"
print(registry[Square], registry[Circle], registry[int], Shape in registry, len(registry))


def passed(k: Any) -> str:
    return k.__name__


print(passed(Square), passed(chosen), passed(type(Square("q"))), passed(str))


# and an Any value that holds a class is a class object where a type[C] location takes it
def typed(k: Any) -> str:
    kind: type[Shape] = k
    return kind("t").name + " " + kind.__name__


print(typed(Square), typed(box), typed(Circle))
back: type[Shape] = box
print(back is Square, back("b").area(), make(box, "m").name)
maybe: type[Shape] | None = None
print(maybe is None, maybe)
maybe = box
print(maybe is Square, maybe is not None)
held: Any = maybe
print(held is Square, held)
held = None
maybe = held
print(maybe)
