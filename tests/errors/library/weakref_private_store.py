# error: 'weakref.ReferenceType' object has no attribute '_handle'
# Assigning another reference's handle would retarget the reference
from _weakref import ref


class Item:
    pass


a = Item()
b = Item()
r = ref(a)
s = ref(b)
r._handle = s._handle
