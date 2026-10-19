# error: vars() or __dict__ of a weakref.ReferenceType object is not supported
# CPython's reference has no __dict__; Pystachy's fields are _weakref's own
from _weakref import ref


class Item:
    pass


item = Item()
print(vars(ref(item)))
