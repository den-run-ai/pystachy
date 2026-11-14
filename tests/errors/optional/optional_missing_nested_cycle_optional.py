# error: the code of module 'absentmods.cyc_b', besides its top-level raise, may raise ImportError
# An optional import of a module that fails through one that imports it back is rejected, as an
# optional import of a failing module that imports its importer back is: CPython runs the handler.
try:
    import absentmods.cyc_a
except ImportError:
    print("fallback")
