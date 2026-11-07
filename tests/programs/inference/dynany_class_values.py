# pystachy: dynamic-any
# Classes are canonical values, distinct from their instances and from metatype.
from typing import Any


class Base:
    pass


class Child(Base):
    pass


class Other:
    pass


def check(value: Any, expected: Any) -> None:
    actual = type(value)
    print(actual is expected, actual == expected, hash(actual) == hash(expected))
    print(type(actual) is type, isinstance(actual, type), id(actual) == id(expected))


check(7, int)
check(True, bool)
check(2.5, float)
check("text", str)
check(None, type(None))
check([1, "two"], list)
check({"one": 1}, dict)
check((1, "two"), tuple)
check(object(), object)
check(Base(), Base)
check(Child(), Child)
check(Other(), Other)
check(Base, type)
check(int, type)
check(type, type)
print(Base is Base, Base is Other, Base == Base(), Base() == Base)
print(isinstance(Base, Base), isinstance(Child, Base), isinstance(Base, type))
print(type(Child()) is Base, type(Child()) is Child, type(True) is int)
classes: list[Any] = [Base, int, type(None), Base]
print(classes[0] is classes[3], classes[1] is type(1), classes[2] is type(None))
print(Base in classes, Other in classes)

# These static type() results do not require boxing bytes or set instances.
bytes_class: Any = type(b"bytes")
set_class: Any = type({1, 2})
print(bytes_class is bytes, type(bytes_class) is type, isinstance(bytes_class, type))
print(set_class is set, type(set_class) is type, isinstance(set_class, type))
for cls in [int, bool, str, list, Base, Child, type(None), type]:
    print(repr(cls), str(cls), cls.__name__, cls.__qualname__, cls.__module__)
    print(type(cls) is type, isinstance(cls, type), type(type(cls)) is type)
