# In a module that opts in to dynamic Any, the class of an object() sentinel, of a range and of
# an iterator is the builtin class that names it, though lib's classes make those objects: their
# type() is that class's value, not a typed class object of lib's class (#7).
# pystachy: dynamic-any
from typing import Any

a = object()
print(type(a) is object, a.__class__ is object, type(a) == object, type(a) is not object, object is type(a))
r = range(3)
print(type(r) is range, range is type(r), type(r) == range, type(r).__name__, type(r).__module__)
t = type(a)
print(t, t is object, t.__name__)
t = type(r)
print(t, t is range, t.__name__)
kept: Any = type(a)
print(kept is object, kept, type(iter([1, 2])).__name__)
