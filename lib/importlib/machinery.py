"""The machinery of importlib: finders, loaders, hooks, etc."""
# Pystachy's subset of CPython 3.13.16's Lib/importlib/machinery.py
# (lib/compatibility.md#importlib): the lists of the file suffixes of modules, which are
# Pystachy's own. It compiles a program's modules from source files and loads neither bytecode
# nor extension modules, so those two lists are empty, where CPython's name its .pyc files and
# the extension modules of its build. The finders and loaders are not here.

SOURCE_SUFFIXES = ['.py']
BYTECODE_SUFFIXES: list[str] = []
EXTENSION_SUFFIXES: list[str] = []


def all_suffixes() -> list[str]:
    """Returns a list of all recognized module suffixes for this process"""
    return SOURCE_SUFFIXES + BYTECODE_SUFFIXES + EXTENSION_SUFFIXES
