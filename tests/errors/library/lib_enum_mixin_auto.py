# error: auto() in an enum class of str and Enum is not supported
# CPython gives such a member the str of Enum's next int ('1')
from enum import Enum, auto


class C(str, Enum):
    A = auto()


print(repr(C.A))
