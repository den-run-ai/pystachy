# from p import * of a package without __all__ binds the submodules imported by then too: here
# the one the package's own code imports. import a.b.c as d takes attribute b of a first: the
# submodule, once its first import has replaced a's own b.
from loader.sp import *

print(X, H, helper.V)
import loader.mid.sub.leaf as L

print(L.V)
