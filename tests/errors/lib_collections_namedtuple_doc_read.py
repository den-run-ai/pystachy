# error: lib_collections_namedtuple_doc_read.py:5: error: reading the __doc__ of NamedTuple Point is not supported (Pystachy keeps no docstrings of classes)
# assigning a namedtuple class's docstring is supported, reading it is not
from collections import namedtuple
Point = namedtuple("Point", "x y")
print(Point.__doc__)
