# error: lib_collections_namedtuple.py:8: error: namedtuple() is only supported as NAME = namedtuple(...) in a module's top-level code, with literal arguments (the compiler makes the class)
# namedtuple() makes its class at compile time, from a module's top-level NAME = namedtuple(...):
# a call anywhere else is rejected
from collections import namedtuple


def point(x, y):
    P = namedtuple("P", "x y")
    return P(x, y)


print(point(1, 2))
