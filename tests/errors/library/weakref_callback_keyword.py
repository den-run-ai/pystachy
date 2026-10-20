# error: ReferenceType.__init__() got some positional-only arguments passed as keyword arguments: 'callback'
# (CPython: TypeError, ref() takes no keyword arguments)
from _weakref import ref


class Item:
    pass


def note(r: ref[Item]) -> None:
    pass


item = Item()
r = ref(item, callback=note)
