# error: cannot compare Plain == collections.deque
# An object of a class of lib/, which stands for a type of CPython's with an equality of its own,
# is not compared by identity with an object whose class has no method (CPython prints False)
from collections import deque


class Plain:
    pass


print(Plain() == deque([1]))
