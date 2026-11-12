# pystachy: dynamic-any
# Builtin classes between Any and typed locations: a builtin class stored as Any is its class
# value, which a location typed type takes back as the class object, the same one that the
# class's name and type(x) give. isinstance() and issubclass() take it there.
from typing import Any


class A:
    pass


def held(k: type) -> str:
    return k.__name__ + " " + k.__module__


values: list[Any] = [int, str, bool, A, type(None), type(5), type("s"), type([1])]
for v in values:
    k: type = v
    print(held(k), k, k is int, k == v, isinstance(3, k), isinstance(True, k), issubclass(k, object), issubclass(k, int))
boxed: Any = float
typed: type = boxed
print(typed, typed is float, typed == boxed, boxed == typed)
back: Any = typed
print(back, back is float, back == float, type(back).__name__)
names: dict[type, str] = {int: "int", A: "A"}
key: Any = int
print(names[key], names[type(7)], key in names, boxed in names)
kinds: list[type] = [int, str]
print(key in kinds, boxed in kinds, kinds.index(key))
