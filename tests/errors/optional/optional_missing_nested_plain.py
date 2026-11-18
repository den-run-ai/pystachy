# error: needs_c.py:6: error: module '_pystachy_absent_c' is not supported: it is not a builtin module
# Only an optional import decides that a module's import of a missing module fails: any other
# import of that module is the error of the import, as before an optional import of it.
try:
    import absentmods.needs_c
except ImportError:
    print("fallback")
import absentmods.needs_c
