# pystachy: dynamic-any
# Python class membership covers every specialization, without choosing its layout.
from typing import Any, Callable, Generic, TypeVar
import templateboxes
from templateboxes import Box as ImportedBox

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def get(self) -> T:
        return self.value


class Plain:
    def __init__(self, value):
        self.value = value


class Unused(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value = value

    def unused(self):
        return memoryview(self.value)


Alias = Box


def membership(value: Any) -> None:
    print(isinstance(value, Box), isinstance(value, ImportedBox),
          isinstance(value, templateboxes.Box), isinstance(value, Plain),
          isinstance(value, Unused), isinstance(value, Alias), isinstance(value, (Box, int)),
          isinstance(value, Box | str), isinstance(value, (Box, type(None))))
    if isinstance(value, Box):
        print(value.value, value.get())


# Compile the predicate before any object of either template is boxed.
membership(None)
number = Box(7)
text = Box("word")
items = [10, 20]
listed = Box(items)
print(isinstance(number, Box), isinstance(text, Box), isinstance(listed, Box))
membership(number)
membership(text)
membership(listed)
membership(templateboxes.typed_box(8))
membership(templateboxes.typed_box("imported"))
membership(Plain(9))
membership(0)
membership("scalar")
membership([1, 2])
membership({"key": 1})
membership(Box)


def increment(value: int) -> int:
    return value + 1


# An erased Callable has no supported type() identity, but is not a Box.
callback: Callable[[int], int] = increment
membership(callback)


def append(value: Any) -> None:
    if isinstance(value, Box):
        value.value.append(30)


append(listed)
print(items, listed.value is items)
print(type(number) is type(text), type(number) is Box)
boxed_number: Any = number
boxed_text: Any = text
print(type(boxed_number) is type(boxed_text), type(boxed_number) is Box)
imported_number: Any = templateboxes.Box(11)
imported_text: Any = templateboxes.Box("other")
boxed_none: Any = None
print(templateboxes.is_box(imported_number), templateboxes.is_box(imported_text),
      templateboxes.is_box(boxed_number), templateboxes.is_box(boxed_none))


class Factory:
    def make(self):
        return Box(1.5)


# Compiling this dynamic method discovers another specialization after the first
# predicate body; the shared dispatcher must be refreshed to include it.
factory: Any = Factory()
membership(factory.make())
