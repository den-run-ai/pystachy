# error: newtype_forward.py:6: error: name 'Later' is not defined (CPython evaluates this NewType's type when the assignment runs)
# CPython evaluates a NewType's type when the assignment runs: a class defined further down is not
# bound yet (NameError).
from typing import NewType

Node = NewType("Node", Later)


class Later:
    pass
