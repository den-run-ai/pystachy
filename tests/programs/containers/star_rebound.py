# A module-level def or class may rebind a function or class that a from-import (also import *)
# bound before it, as socket's def getaddrinfo after from _socket import *, where nothing reads
# the import's binding in between: the def or class binds the name for all of the module's code
# and for the modules that import it, and a function defined in between that reads the name runs
# only later. Here the star import binds helper as mods.star_over re-exports it, the from-import
# as mods.star_base defines it; both are rebound, Base by a class.
import mods.star_over as over
from mods.star_over import *
from mods.star_base import helper, Shape as Base


def helper() -> str:
    return "main helper, not " + over._base.helper()


class Base(over.Shape):
    def area(self) -> int:
        return 100 * self.n


print(greet("ann"))
print(shout("bob"))
print(Shape(3).area(), Shape(1).twice().area(), isinstance(Shape(1), over._base.Shape))
print(over.greet("cy"), over.Shape(2).area(), over.helper(), LIMIT)
print(helper(), Base(1).area(), isinstance(Base(1), over.Shape))
try:
    raise Error("boom")
except over._base.Error as e:
    print("caught", type(e).__name__, e, isinstance(e, over.Error))
