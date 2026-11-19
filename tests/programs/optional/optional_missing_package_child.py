# An optional import of a package whose code imports its own submodule, whose top-level import
# of a module that is not found fails: both modules' code runs up to the failing import, then the
# handler runs, as in CPython (the compiler once looked for the failure in the package for ever).
try:
    import absentmods.selfpkg
    print("not reached")
except ImportError:
    print("fallback: selfpkg")
print("done")
