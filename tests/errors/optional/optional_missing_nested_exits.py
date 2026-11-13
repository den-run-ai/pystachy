# error: module '_pystachy_absent_c' is not supported: it is not a builtin module and there is no _pystachy_absent_c.py on the module path (module 'absentmods.needs_c' needs it); an optional import whose except clause may end the program needs its module
# A handler that may end the program makes the module required, as where the module itself is
# not found: CPython may have the module that Pystachy does not find.
import sys

try:
    import absentmods.needs_c
except ImportError:
    sys.exit("this program needs needs_c")
print("have needs_c")
