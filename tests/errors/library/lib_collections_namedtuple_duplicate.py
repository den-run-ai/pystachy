# error: lib_collections_namedtuple_duplicate.py:4: error: Encountered duplicate field name: 'x'
# CPython's ValueError
from collections import namedtuple
Point = namedtuple("Point", "x y, x")
print(Point(1, 2, 3))
