# error: _weakref.ref() prototype does not support exception or slotted instances
from _weakref import ref


class Slotted:
    __slots__ = ("value",)

    def __init__(self):
        self.value = 1


ref(Slotted())
