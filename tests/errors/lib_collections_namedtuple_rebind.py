# error: lib_collections_namedtuple_rebind.py:4: error: namedtuple() is only supported as NAME = namedtuple(...), where nothing else binds NAME
# the name a namedtuple() class is assigned to names that class only
from collections import namedtuple
Point = namedtuple("Point", "x y")
print(Point(1, 2))
Point = namedtuple("Point", "x y z")
print(Point(1, 2, 3))
