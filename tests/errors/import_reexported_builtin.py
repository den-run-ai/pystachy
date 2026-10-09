# error: 'os' is read in f() where Pystachy cannot tell that the import in it that binds 'os' has run
# from emods.reexp_os import os imports a Python module, so it binds os in f only, where the read
# before it finds os unbound (CPython: UnboundLocalError), not the module's os.
import os


def f() -> str:
    s = os.sep
    from emods.reexp_os import os
    return s


print(f())
