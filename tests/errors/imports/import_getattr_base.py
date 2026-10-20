# error: import_getattr_base.py:7: error: the special method __getattr__ of its base emods.attrhooks.LazyError is not supported (CPython calls it for each attribute it does not find)
# A class of the program that inherits __getattr__ from a base of an imported module is an error
# at its class statement, which names the base.
from emods.attrhooks import LazyError


class Retry(LazyError):
    pass


try:
    raise Retry("again", False)
except Retry as e:
    print(e.depth)
