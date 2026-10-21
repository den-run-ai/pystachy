# error: import_getattr_except_tuple.py:6: error: class emods.attrhooks.LazyError is not supported: the special method __getattr__ is not supported (CPython calls it for each attribute it does not find)
from emods.attrhooks import LazyError, double

try:
    print(double(2))
except (ValueError, LazyError):
    print("caught")
