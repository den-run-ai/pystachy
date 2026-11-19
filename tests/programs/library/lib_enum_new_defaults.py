# An enum __new__ whose parameters have defaults that members' values leave out.
from enum import Enum, IntEnum


class Kind(IntEnum):
    A = (1, "one")
    B = (2, "two", "second")

    def __new__(cls, value, phrase, description=""):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.phrase = phrase
        obj.description = description
        return obj


for k in Kind:
    print(k, k.value, k.phrase, repr(k.description))
