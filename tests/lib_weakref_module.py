# The weakref module imports: its ref and ReferenceType are _weakref's, callbacks included, also by
# from-imports and a star import. Its weak containers, WeakMethod, finalize, proxies and counts are
# not supported (tests/errors/lib_weakref_*.py).
import weakref
from weakref import ref, ReferenceType


class Item:
    def __init__(self, value: int):
        self.value = value


calls: list[int] = [0]


def note(r: weakref.ReferenceType[Item]) -> None:
    calls[0] += 1


item = Item(1)
r = weakref.ref(item)
s = ref(item, note)
t = ReferenceType(item)
print(r() is item, s() is item, t() is item, r == s, hash(r) == hash(item))
print(type(r).__name__, type(r).__module__, calls[0])
print(weakref.__doc__.splitlines()[0])
