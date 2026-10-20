# error: lib_collections_namedtuple_mixed.py:5: error: expected Point[int, int], got Point[str, str]
# objects of two specializations of a namedtuple class (fields of other types) in one list
from collections import namedtuple
Point = namedtuple("Point", "x y")
ps = [Point(1, 2), Point("a", "b")]
print(ps)
