# error: lib_collections_namedtuple_number_field.py:4: error: namedtuple() is only supported with field names that are a string literal or a list or tuple of string literals (the compiler makes the class)
# Every field name must be a string literal.
from collections import namedtuple
Point = namedtuple("Point", ["x", 1, "z"])
print(Point(1))
