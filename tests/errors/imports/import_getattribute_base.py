# error: import_getattribute_base.py:7: error: class emods.attrhooks.LoggedRetry is not supported: the special method __getattribute__ of its base emods.attrhooks.LoggedError is not supported (CPython calls it to read each attribute)
# A class of an imported module that inherits __getattribute__ from its base is an error where the
# program uses it, as one that defines it is.
from emods.attrhooks import LoggedRetry

try:
    raise LoggedRetry("again")
except Exception as e:
    print(e)
