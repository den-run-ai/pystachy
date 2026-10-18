# error: ref.__init__() takes 2 positional arguments but 3 were given
from _weakref import ref


class Item:
    pass


def callback(value) -> None:
    pass


ref(Item(), callback)
