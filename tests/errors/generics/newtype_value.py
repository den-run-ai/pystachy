# error: newtype_value.py:7: error: type alias 'UserId' cannot be used as a value (only annotations may name it)
# A NewType is a type in annotations and a call that returns its argument: other uses of it as a
# value (its repr, __supertype__) are not supported.
from typing import NewType

UserId = NewType("UserId", int)
print(UserId)
