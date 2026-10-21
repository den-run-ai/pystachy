# error: import_getattribute_except_base.py:7: error: class emods.attrhooks.LoggedRetry is not supported: the special method __getattribute__ of its base emods.attrhooks.LoggedError is not supported (CPython calls it to read each attribute)
# (a class that inherits the hook from its base, named only by an except clause that binds it)
from emods.attrhooks import LoggedRetry

try:
    print("try")
except LoggedRetry as e:
    print(e.code)
