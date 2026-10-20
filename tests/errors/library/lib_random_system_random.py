# error: module 'random' has no attribute 'SystemRandom'
# lib/random makes SystemRandom where os.urandom() imports (lib/README.md): Pystachy's os has no
# urandom(), and Pystachy compiles no subclass of Random
import random

print(random.SystemRandom().random())
