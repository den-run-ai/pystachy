# error: lib_collections_namedtuple_nested_list.py:4: error: namedtuple() is only supported with field names that are a string literal or a list or tuple of string literals (the compiler makes the class)
# A nested list is not a field name, even when the outer sequence is a tuple.
from collections import namedtuple
Point = namedtuple("Point", ("x", ["y"], "z"))
print(Point(1))
