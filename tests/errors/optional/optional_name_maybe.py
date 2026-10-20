# error: cannot tell whether module 'eload.maybe_val' has bound 'val' when this optional import runs
# Whether the except clause runs depends on a branch of the module's code (CPython: it runs here).
try:
    from eload.maybe_val import val
except ImportError:
    val = 2
print(val)
