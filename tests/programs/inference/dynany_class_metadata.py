# pystachy: dynamic-any
from typing import Any


class C:
    __module__ = "wire"
    __qualname__ = "Outer.C"


class Child(C):
    pass


print(C.__module__, C.__qualname__)
cls: Any = C
print(cls.__name__, cls.__module__, cls.__qualname__, repr(cls))
print(type(C()).__module__, type(C()).__qualname__)
obj: Any = C()
print(type(obj).__module__, type(obj).__qualname__)
print(type(obj) is C, obj.__class__ is cls)
print(Child.__module__, Child.__qualname__)
child_class: Any = Child
print(child_class.__module__, child_class.__qualname__, repr(child_class))
child: Any = Child()
print(type(child).__module__, type(child).__qualname__)
print(type(child) is child_class, type(child) is not cls)
