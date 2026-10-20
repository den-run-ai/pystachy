# error: import_getattr_except.py:8: error: class emods.attrhooks.LazyError is not supported: the special method __getattr__ is not supported (CPython calls it for each attribute it does not find)
# A class of an imported module that defines __getattr__ is an error also where the program only
# names it in an except clause.
import emods.attrhooks

try:
    print(emods.attrhooks.double(2))
except emods.attrhooks.LazyError:
    print("caught")
