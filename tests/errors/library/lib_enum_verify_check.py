# error: @verify() of an enum class is supported with enum's UNIQUE, CONTINUOUS and NAMED_FLAGS
# CPython's verify() ignores a check that is none of EnumCheck's members (printing [<C.A: 1>])
from enum import Enum, verify


@verify("one name per value")
class C(Enum):
    A = 1


print(list(C))
