# error: import_getattr.py:6: error: class emods.attrhooks.Lazy is not supported: the special method __getattr__ is not supported (CPython calls it for each attribute it does not find)
# A class of an imported module that defines __getattr__ is an error where the program uses it
# (CPython calls it where reading a field fails); the rest of the module compiles.
from emods.attrhooks import Lazy, double
print(double(2))
print(Lazy(False).depth)
