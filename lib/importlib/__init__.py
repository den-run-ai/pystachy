"""A pure Python implementation of import."""
# Pystachy's subset of CPython 3.13.16's Lib/importlib (lib/compatibility.md#importlibmetadata):
# the package of its module metadata. Pystachy resolves a program's imports while it compiles
# the program, so nothing imports a module at run time: import_module(), reload(),
# invalidate_caches() and __import__() are not here.
