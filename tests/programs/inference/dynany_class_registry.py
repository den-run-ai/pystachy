# pystachy: dynamic-any
# Registration through a parameter must keep unrelated callback identities/types.
from typing import Any


class Entry:
    def __init__(self, value: int) -> None:
        self.value = value


class Child(Entry):
    pass


REGISTRY: dict[Any, Any] = {}


def register(cls: Any, callback: Any) -> None:
    REGISTRY[cls] = callback


def integer(value: int) -> str:
    return "int:" + str(value)


def text(value: str) -> str:
    return "str:" + value


def entry(value: Entry) -> str:
    return "entry:" + str(value.value)


def child(value: Child) -> str:
    return "child:" + str(value.value)


def nothing(value: Any) -> str:
    return "none:" + str(value)


def encode(value: Any) -> str:
    return REGISTRY[type(value)](value)


register(int, integer)
register(str, text)
register(Entry, entry)
register(Child, child)
register(type(None), nothing)
print(encode(12), encode("hello"), encode(Entry(3)), encode(Child(4)), encode(None))
print(len(REGISTRY), REGISTRY[type(1)] is integer, REGISTRY[type("a")] is text)
print(type(True) in REGISTRY, bool in REGISTRY, Entry in REGISTRY, Child in REGISTRY)
try:
    print(encode(True))
except KeyError:
    print("missing bool")
print(REGISTRY.get(float) is None)
register(int, nothing)
print(encode(2), encode("again"), len(REGISTRY))
del REGISTRY[Child]
print(Child in REGISTRY, Entry in REGISTRY)
try:
    print(encode(Child(5)))
except KeyError:
    print("missing child")
