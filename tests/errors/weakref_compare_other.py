# error: expected ReferenceType[Item], got int
# A reference compares with references to the same type; CPython's comparison with another
# object returns False
from _weakref import ref


class Item:
    pass


item = Item()
print(ref(item) == 5)
