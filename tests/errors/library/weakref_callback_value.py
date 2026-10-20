# error: ReferenceType() cannot bind its type variables from the argument for 'callback', a int
# A callback must be a function or None here. CPython takes any object, and reports the TypeError
# of calling it as an exception it ignores once the referent dies.
from _weakref import ref


class Item:
    pass


item = Item()
r = ref(item, 5)
