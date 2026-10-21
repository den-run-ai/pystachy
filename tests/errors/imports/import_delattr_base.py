# error: import_delattr_base.py:5: error: the special method __delattr__ of its base emods.attrhooks.KeptError is not supported (CPython calls it to delete each attribute)
from emods.attrhooks import KeptError


class Retry(KeptError):
    pass


print(Retry("again"))
