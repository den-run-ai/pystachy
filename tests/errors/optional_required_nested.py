# error: needs_absent.py:1: error: module 'yaml' is not supported
# A module that requires a module Pystachy does not find (its handler raises) is not taken as
# failing for sure, so an optional import of it is an error where its code is compiled.
try:
    import eload.needs_absent
except ImportError:
    print("fallback")
print("done")
