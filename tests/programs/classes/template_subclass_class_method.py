# A class method that a class inherits from a class template, called through an object of the
# class: cls is the object's class, as through the class's name, so cls.__name__, a class
# attribute the class binds again, cls(...) and another class or static method called through
# cls are the class's. For a subclass without an __init__, one whose own __init__ is a class
# template too, one under such a subclass, and a class deriving from a generic class's
# specialization (#1744). An object of the template itself still reads the template. Every
# object the methods are called through is of a class that no class derives from: through one
# of a class that others derive from the program is compiled as before
# (template_subclass_class_method_location.py)
from typing import Generic, TypeVar


class Style:
    tag = "base"
    count = 0

    def __init__(self, fmt):
        self.fmt = fmt

    def who(self) -> str:
        return type(self).__name__

    @staticmethod
    def mark() -> str:
        return "*"

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @classmethod
    def what(cls, suffix: str = "?") -> str:
        return cls.tag + suffix

    @classmethod
    def make(cls, fmt: int):
        return cls(fmt)

    @classmethod
    def both(cls) -> str:
        return cls.mark() + cls.name() + cls.what("!")

    @classmethod
    def seen(cls) -> int:
        return cls.count


class Plain(Style):
    pass


class Tagged(Style):
    tag = "tagged"


class Own(Style):
    tag = "own"

    def __init__(self, fmt):
        Style.__init__(self, fmt)
        self.extra = 1


class Mid(Style):
    tag = "mid"


class Deep(Mid):
    pass


def through(x) -> str:
    return x.name() + "/" + x.what() + "/" + x.make(4).who() + "/" + x.both() + "/" + str(x.seen())


Style.count = 5
print(through(Style(1)))
print(through(Plain(2)))
print(through(Tagged(3)))
print(through(Own(4)))
print(through(Deep(6)))
print(through(Tagged("s")), Tagged("t").make(7).fmt)
print(Plain.name(), Tagged.what(), Own.make(1).who(), Deep.both(), Mid.seen())
t = Tagged(8)
o = Own(9)
print(t.name(), t.what("."), t.make(1).who(), o.name(), o.make(2).extra, o.both())

T = TypeVar("T")


class Box(Generic[T]):
    kind = "box"

    def __init__(self, v: T) -> None:
        self.v = v

    @classmethod
    def label(cls) -> str:
        return cls.__name__ + ":" + cls.kind

    @classmethod
    def twice(cls) -> str:
        return cls.label() + cls.label()


class IntBox(Box[int]):
    kind = "int"


class StrBox(Box[str]):
    pass


print(Box(1).label(), IntBox(2).label(), StrBox("s").label(), IntBox.label(), StrBox.twice())
b = IntBox(3)
print(b.twice(), Box("x").twice(), b.v)
