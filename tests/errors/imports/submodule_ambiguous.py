# error: 'eload.sub.util' is the package's own 'util' until the program's first import of its submodule
import eload.other
from eload.sub import util
print(len(util))
