# error: Enum() takes no arguments
# CPython's functional API makes a new enum class (printing C.A)
from enum import Enum


C = Enum("C", "A B")
print(C.A)
