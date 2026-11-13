"""A pure Python implementation of import."""
# Pystachy's subset of CPython 3.13.16's Lib/importlib (lib/compatibility.md#importlibmetadata):
# the package of its module metadata, and import_module() of a module that a string constant
# names. Pystachy resolves a program's imports while it compiles the program, so nothing
# imports a module at run time: reload(), invalidate_caches() and __import__() are not here.

__all__ = ['import_module']


class _module_named_by_a_string_constant:
    pass


def import_module(name: _module_named_by_a_string_constant, package: _module_named_by_a_string_constant | None = None):
    """Import a module.

    The 'package' argument is required when performing a relative import. It
    specifies the package to use as the anchor point from which to resolve the
    relative import to an absolute import.

    """
    # Pystachy port: the compiler writes the import statement of a call that a string constant
    # names the module of (mod = import_module("a.b"): Loader.import_calls), and the call is
    # then not here. A call compiled here names its module some other way, or is no statement
    # that binds a variable: its arguments are not of this parameter's type, which is the
    # compile-time error.
    return name
