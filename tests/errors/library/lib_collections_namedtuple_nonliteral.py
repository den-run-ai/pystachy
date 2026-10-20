# error: lib_collections_namedtuple_nonliteral.py:5: error: namedtuple() is only supported with field names that are a string literal or a list or tuple of string literals (the compiler makes the class)
# the compiler makes the class from literal arguments only
from collections import namedtuple
FIELDS = "x y"
Point = namedtuple("Point", FIELDS)
print(Point(1, 2))
