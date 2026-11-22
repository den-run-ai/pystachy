# error: class_nested_enum_attr.py:12: error: 'Outer' object has no attribute 'Kind': Outer.Kind, a class nested in its body, is read as Outer.Kind here (an enum class, or one nested in a dataclass or NamedTuple, is no class attribute)
# An enum class nested in a class body is no class attribute here: CPython's self.Kind is the
# class, which Outer.Kind reads.
from enum import Enum


class Outer:
    class Kind(Enum):
        A = 1

    def show(self) -> None:
        print(self.Kind.A)


Outer().show()
