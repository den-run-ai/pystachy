# error: import_module_getattr_from.py:4: error: cannot import name 'missing' from 'emods.modhook'
# A from-import of a name that only the module's __getattr__ (PEP 562) would give stays an error:
# Pystachy calls a class's __getattr__ (#1536), not a module's.
from emods.modhook import double, missing

print(double(2), missing)
