"""A module for Python 2 only: its NameError shim raises ImportError (tests/programs/language/name_error_shims.py)."""
try:
    unicode  # noqa: F821
except NameError:
    raise ImportError("mods.py2only needs Python 2")
VERSION = 2
