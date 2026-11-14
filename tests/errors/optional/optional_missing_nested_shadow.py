# error: shadow.py:7: error: module '_pystachy_absent_c' is not supported: it is not a builtin module
# A module that binds the name ModuleNotFoundError itself is not taken as failing at its import
# of a missing module: that import stays an error, also for an optional import of the module.
try:
    import absentmods.shadow
except ImportError:
    print("fallback")
