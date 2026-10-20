# error: import_setattr.py:5: error: class emods.attrhooks.Frozen is not supported: the special method __setattr__ is not supported (CPython calls it to assign each attribute)
# (CPython's Frozen(1) raises AttributeError in __init__)
from emods.attrhooks import Frozen

f = Frozen(1)
print(f.x)
