# pystachy: dynamic-any
# Builtin constructor aliases retain their static calls and canonical identity.
from typing import Any


constructor = int
boxed: Any = constructor
print(constructor("17"), int("19"))
print(type(constructor) is type, type(boxed) is type)
print(id(constructor) == id(boxed), hash(constructor) == hash(boxed))
print(id(int) == id(type(1)), hash(int) == hash(type(1)))
print(constructor is boxed, boxed is int, constructor == boxed, boxed == int)
print(repr(constructor), str(constructor), bool(constructor))
print(constructor, f"{int}", f"{int!r}", format(int), "%s" % int)
print(constructor.__name__, constructor.__qualname__, constructor.__module__)
print(int.__name__, int.__qualname__, int.__module__)
print(type.__name__, type.__qualname__, type.__module__)
print(repr(object), repr(range), repr(bytes), repr(set))
print(id(object) == id(type(object())), hash(object) == hash(type(object())))
print(id(range) == id(type(range(3))), hash(range) == hash(type(range(3))))
try:
    print(format(int, ">20"))
except TypeError as exc:
    print(str(exc))
