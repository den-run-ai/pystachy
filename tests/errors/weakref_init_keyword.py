# error: ref() takes no keyword arguments
# r.__init__() checks its arguments as CPython's does, and changes nothing
from _weakref import ref


class Item:
    pass


item = Item()
r = ref(item)
r.__init__(item, callback=None)
