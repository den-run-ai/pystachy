# error: star_rebound_base.py:7: error: 'Shape' is bound both by an import and by a def or class, and is read here in between (not supported)
# CPython's class Shape(Shape) subclasses the Shape that import * bound; Pystachy binds Shape only
# by the class statement.
from emods.star_base import *


class Shape(Shape):
    pass


print(Shape(2).n)
