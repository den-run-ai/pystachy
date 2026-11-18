# pystachy: dynamic-any
# Documented deviation: what a class object held as an Any value gives for a name is compiled
# for class attributes, static methods and class methods. A method of the class's objects, a
# property, a static method read without a call, and a member whose use needs a layout that no
# Any value holds (a typed list, an object of a class nothing else boxes) raise
# NotImplementedError where they are selected: CPython gives a function, a property object and
# the values. They do not raise the AttributeError of a missing name, which getattr()'s default
# would take. The names every class object has of type keep the dynamic lookup's AttributeError.
from typing import Any


class Hidden:
    def __init__(self) -> None:
        self.v = 1


class Widget:
    """A widget."""
    words = ["a", "b"]
    size = 3

    def __init__(self) -> None:
        self.w = 2

    def show(self) -> str:
        return "show"

    @property
    def area(self) -> int:
        return 9

    @staticmethod
    def kind() -> str:
        return "widget"

    @staticmethod
    def build() -> Hidden:
        return Hidden()

    @staticmethod
    def typed(d: dict[str, list[int]]) -> int:
        return len(d)


def attempt(what: str, k: Any) -> None:
    try:
        if what == "show":
            print(k.show)
        elif what == "showcall":
            print(k.show())
        elif what == "area":
            print(k.area)
        elif what == "kind":
            print(k.kind)
        elif what == "words":
            print(k.words)
        elif what == "build":
            print(k.build())
        elif what == "typed":
            print(k.typed({}))
        elif what == "doc":
            print(k.__doc__)
        elif what == "default":
            print(getattr(k, "show", "no show"))
        elif what == "size":
            print(k.size, k.kind(), getattr(k, "size", 0), getattr(k, "absent", "absent"))
    except NotImplementedError as e:
        print(what, "NotImplementedError:", e)
    except AttributeError as e:
        print(what, "AttributeError:", e)


k: Any = Widget
for what in ["show", "showcall", "area", "kind", "words", "build", "typed", "doc", "default", "size"]:
    attempt(what, k)
