# error: lib_collections_namedtuple_defaults.py:4: error: Got more default values than field names
# CPython's TypeError
from collections import namedtuple
Point = namedtuple("Point", "x y", defaults=(0, 0, 0))
print(Point())
