# error: import_delattr.py:4: error: class emods.attrhooks.Kept is not supported: the special method __delattr__ is not supported (CPython calls it to delete each attribute)
from emods.attrhooks import Kept

print(Kept(1).x)
