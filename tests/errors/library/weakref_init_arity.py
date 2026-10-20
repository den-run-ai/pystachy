# error: __init__ expected at most 2 arguments, got 3
from _weakref import ref


class Item:
    pass


item = Item()
r = ref(item)
r.__init__(item, None, None)
