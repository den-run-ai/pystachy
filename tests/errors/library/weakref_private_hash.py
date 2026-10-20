# error: 'weakref.ReferenceType' object has no attribute '_hash'
# The cached hash is _weakref's own too
from _weakref import ref


class Item:
    pass


item = Item()
r = ref(item)
r._hash += 1
