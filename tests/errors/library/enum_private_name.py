# error: enum class E's _E__value is not supported
# Preserve the existing private-enum-member rejection after lexical mangling.
from enum import Enum


class E(Enum):
    __value = 1


print(E)
