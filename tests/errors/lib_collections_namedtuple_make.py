# error: lib_collections_namedtuple_make.py:5: error: Point._make() of a tuple of 3 items is not supported: it raises TypeError: Expected 2 arguments, got 3
# _make() of a tuple whose length is not the number of fields
from collections import namedtuple
Point = namedtuple("Point", "x y")
print(Point._make((1, 2, 3)))
