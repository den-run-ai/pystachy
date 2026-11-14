# error: newtype_arguments.py:7: error: NewType 'UserId' takes exactly one positional argument
# A NewType's call takes its one argument (CPython raises TypeError for others).
from typing import NewType

UserId = NewType("UserId", int)

print(UserId(1, 2))
