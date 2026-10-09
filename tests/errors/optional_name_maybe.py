# error: 'val' may or may not be bound in module 'eload.maybe_val' when this optional import runs
# Whether the except clause runs depends on a branch of the module's code (CPython: it runs here).
try:
    from eload.maybe_val import val
except ImportError:
    val = 2
print(val)
