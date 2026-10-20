# error: maybeown/__init__.py:5: error: 'util' is the package's own 'util' if its code has bound it before this import, else the submodule 'eload.maybeown.util', and Pystachy cannot tell which (not supported)
# The package binds util only in an if before its own from . import util.
import eload.maybeown
