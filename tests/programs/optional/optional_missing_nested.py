# An optional import of a module whose own top-level import of a module that is not found fails
# (CPython's ssl without _ssl): the module's code runs up to that import, then the handler runs,
# as where the module itself is not found. That holds through a module that imports such a
# module, and a later import runs the code again. The statements after the failing import never
# run: they may use what the missing module would bind.
try:
    import absentmods.needs_c
    print("not reached")
except ImportError:
    print("fallback: needs_c")
try:
    from absentmods import through
except ModuleNotFoundError:
    print("fallback: through")
try:
    import absentmods.needs_c as again
except ImportError:
    again = None
print(again is None)
try:
    from absentmods.frompkg import thing
except ImportError:
    thing = 0
print(thing)
print("done")
