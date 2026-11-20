# error: @verify(CONTINUOUS) of enum class Letter: can only concatenate str (not "int") to str (CPython's TypeError)
# CPython's TypeError where @verify(CONTINUOUS) runs: the values between strs are no ints
from enum import CONTINUOUS, Enum, verify


@verify(CONTINUOUS)
class Letter(Enum):
    A = "a"
    B = "b"


print(list(Letter))
