# error: collections_abc_optional_helper.py:5: error: collections.abc.bytes_iterator is not supported: Pystachy's collections.abc (which _collections_abc is too) has only the ABCs
# a name that CPython's module binds and Pystachy's lacks: rejected, as CPython would not run the
# except clause (an ImportError there would run it)
try:
    from _collections_abc import bytes_iterator
except ImportError:
    bytes_iterator = None
print(bytes_iterator)
