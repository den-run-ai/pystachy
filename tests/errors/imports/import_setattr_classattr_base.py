# error: import_setattr_classattr_base.py:5: error: the special method __setattr__ of its base emods.attrhooks.SealedError is not supported (CPython calls it to assign each attribute)
from emods.attrhooks import SealedError


class Retry(SealedError):
    pass


print("done")
