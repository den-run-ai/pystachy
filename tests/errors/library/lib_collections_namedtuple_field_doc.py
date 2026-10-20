# error: lib_collections_namedtuple_field_doc.py:6: error: assigning the __doc__ of namedtuple field Point.x is only supported with a string literal (Pystachy keeps no docstrings of classes)
# a field's docstring other than a string literal: CPython evaluates it
from collections import namedtuple
Point = namedtuple("Point", "x y")
DOC = "The x coordinate"
Point.x.__doc__ = DOC
print(Point(1, 2))
