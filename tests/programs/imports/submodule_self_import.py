# A package's own "from . import util" takes the submodule where the package has not bound
# util yet, and the package's util where it has.
import loader.selfimp

print(loader.selfimp.util, loader.selfimp.u.V)
