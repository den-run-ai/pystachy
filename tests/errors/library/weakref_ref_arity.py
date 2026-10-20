# error: ReferenceType.__init__() takes from 2 to 3 positional arguments but 4 were given
# (CPython: TypeError, __new__ expected at most 2 arguments, got 3)
from _weakref import ref


class Item:
    pass


def note(r: ref[Item]) -> None:
    pass


item = Item()
r = ref(item, note, note)
