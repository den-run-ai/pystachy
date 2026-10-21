"""A module whose try reads a name that the module it imports first assigns through it, in a
circular import, as CPython runs it (tests/programs/language/name_error_shims_bound.py)."""
import mods.shim_b

try:
    seen = flag
except NameError:
    seen = 0
flag = 2
