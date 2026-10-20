# error: import_getattribute.py:5: error: class emods.attrhooks.Logged is not supported: the special method __getattribute__ is not supported (CPython calls it to read each attribute)
import emods.attrhooks

print(emods.attrhooks.double(2))
print(emods.attrhooks.Logged(1).x)
