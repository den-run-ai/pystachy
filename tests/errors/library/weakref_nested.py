# error: cannot create weak reference to a weakref.ReferenceType object
from _weakref import ref


class Item:
    pass


obj = Item()
r = ref(obj)
ref(r)
