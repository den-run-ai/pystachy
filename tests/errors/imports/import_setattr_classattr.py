# error: import_setattr_classattr.py:6: error: class emods.attrhooks.SealedError is not supported: the special method __setattr__ is not supported (CPython calls it to assign each attribute)
# (CPython's SealedError("x") raises TypeError where its __init__ assigns self.code)
from emods.attrhooks import SealedError

try:
    raise SealedError("x")
except TypeError as e:
    print(e)
