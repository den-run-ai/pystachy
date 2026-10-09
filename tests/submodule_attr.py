# A package's name that is also the name of one of its submodules (issue #13): the first import of
# the submodule binds the name in the package to it, unless the package's own code imports the
# submodule before it binds the name (from .util import util); import P.x as y binds y to the
# package's attribute x, as from P import x as y does. Where the order the program runs decides
# which one a name is, the program is rejected (tests/errors/submodule_*.py).
import loader.own.util as u
import loader.own
from loader.own import util
print(u(), util(), loader.own.util())
import loader.var.util as vu
print(vu.V)
import loader.early
from loader.early import util as eu
print(loader.early.util, loader.early.V, eu)
import loader.plain
print(loader.plain.util)
