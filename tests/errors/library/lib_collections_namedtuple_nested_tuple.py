# error: lib_collections_namedtuple_nested_tuple.py:4: error: namedtuple() is only supported with field names that are a string literal or a list or tuple of string literals (the compiler makes the class)
# A nested tuple must not silently truncate the field list at its first non-string.
from collections import namedtuple
Point = namedtuple("Point", ["x", ("y",), "z"])
print(Point(1))
