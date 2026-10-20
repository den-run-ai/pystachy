"""A Python 2 shim that the module it imports first (tests/mods/shim_d.py) makes moot, through
the module, in a circular import: the try runs as CPython runs it (tests/programs/language/name_error_shims_bound.py)."""
import mods.shim_d

try:
    unicode
except NameError:
    unicode = str
    seen = "NameError"
else:
    seen = "bound"
