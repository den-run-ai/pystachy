# error: import_module_getattr.py:8: error: module 'emods.modhook' has no attribute 'missing'
# Pystachy calls a class's __getattr__ (#1536), not a module's (PEP 562): a name that the module
# does not bind stays an error, where CPython calls the module's function for it.
import emods.modhook

print(emods.modhook.double(2))
print(emods.modhook.__getattr__("x"))
print(emods.modhook.missing)
