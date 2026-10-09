# error: 'emods' is read in k() where the import in it that binds 'emods' may not have run
# The import in the function makes emods its local, unbound where the branch does not run
# (CPython: UnboundLocalError), though the module imports emods too.
import sys
import emods.mod


def k() -> int:
    if len(sys.argv) > 5:
        import emods.mod
    return emods.mod.VALUE


print(k())
