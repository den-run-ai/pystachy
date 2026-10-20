# error: 'from eload.subs import *' binds 'util' to the submodule 'eload.subs.util' only if an import of it has run before, and Pystachy cannot tell whether one has (not supported)
from eload.subs import *
import eload.subs.util

print(util.V)
