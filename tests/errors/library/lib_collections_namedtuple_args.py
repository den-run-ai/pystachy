# error: lib_collections_namedtuple_args.py:4: error: namedtuple() takes 2 positional arguments but 3 were given
# rename, defaults and module are keyword-only: CPython's TypeError
from collections import namedtuple
Point = namedtuple("Point", "x y", True)
print(Point(1, 2))
