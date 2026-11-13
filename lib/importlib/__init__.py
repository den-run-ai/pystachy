"""A pure Python implementation of import."""
# Pystachy's subset of CPython 3.13.16's Lib/importlib (lib/compatibility.md#importlibmetadata):
# the package of its module metadata, and import_module() of a module that a string constant
# names. Pystachy resolves a program's imports while it compiles the program, so nothing
# imports a module at run time: reload(), invalidate_caches() and __import__() are not here.

def import_module(name, package=None):
    """Import a module.

    The 'package' argument is required when performing a relative import. It
    specifies the package to use as the anchor point from which to resolve the
    relative import to an absolute import.

    """
    # Pystachy port: the compiler writes the import statement of a call that a string constant
    # names the module of (mod = import_module("a.b"): Loader.import_calls), and the call is
    # then not here. A call compiled here names its module some other way, or is no statement
    # that binds a variable, and is the compiler's error (call_fn). (__all__ is left out:
    # a module imports the function by name.)
    return name
