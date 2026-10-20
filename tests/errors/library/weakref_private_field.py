# error: 'weakref.ReferenceType' object has no attribute '_handle'
# A reference's fields are _weakref's own: CPython's reference has no such attribute
from _weakref import ref


class Item:
    pass


item = Item()
r = ref(item)
print(r._handle)
