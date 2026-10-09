# error: submodule_star_variable.py:5: error: 'sub' is bound both as a variable and by an import (not supported)
# The star import binds sub to the submodule the package's own code imports, over the variable.
sub = 5
print(sub)
from eload.starsub import *

print(sub.S, S, P)
