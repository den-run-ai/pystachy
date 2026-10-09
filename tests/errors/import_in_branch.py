# error: 'emods' is read in k() where Pystachy cannot tell that the import in it that binds 'emods' has run
# The import in the function makes emods its local, unbound where the branch does not run
# (CPython: UnboundLocalError), though the module imports emods too.
import sys
import emods.mod


def k() -> int:
    if len(sys.argv) > 5:
        import emods.mod
    return emods.mod.VALUE


print(k())
