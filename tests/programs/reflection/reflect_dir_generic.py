# dir() and hasattr() (literal and run-time names) of generic classes, which have the attributes
# Generic gives (__class_getitem__, __orig_bases__, __parameters__) and, with PEP 695's syntax,
# __type_params__; a dataclass without fields has no __annotations__;
# a slot __init__ may leave unassigned is listed by dir() (its descriptor is the class's)
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


class Box[U]:
    def __init__(self, item: U) -> None:
        self.item = item


class Gen(Generic[T]):
    def __init__(self, item: T) -> None:
        self.item = item


class Plain:
    pass


@dataclass
class Empty:
    pass


@dataclass
class Point:
    x: int


class Slots:
    __slots__ = ("a", "b")

    def __init__(self, f: bool) -> None:
        self.a = 1
        if f:
            self.b = 2


base = set(dir(Plain()))
print(sorted(set(dir(Box(1))) - base))
print(sorted(set(dir(Gen("s"))) - base))
print(hasattr(Box(1), "__type_params__"), hasattr(Gen(1), "__type_params__"), hasattr(Gen(1), "__orig_bases__"))
print(hasattr(Box("s"), "__parameters__"), hasattr(Plain(), "__class_getitem__"))
names = "item __class_getitem__ __orig_bases__ __parameters__ __type_params__ zz".split()
for o in [Box(1.5)]:
    print([n for n in names if hasattr(o, n)])
print([n for n in names if hasattr(Gen([1]), n)])
print(sorted(set(dir(Empty())) - base), sorted(set(dir(Point(1))) - base))
print(hasattr(Empty(), "__annotations__"), hasattr(Point(1), "__annotations__"))
for f in [True, False]:
    s = Slots(f)
    print(dir(s)[-2:], hasattr(s, "b"), [n for n in ["a", "b"] if hasattr(s, n + "")])
