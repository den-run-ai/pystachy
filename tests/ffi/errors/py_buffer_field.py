# error: tests/ffi/errors/py_buffer_field.py:4: error: 'Buffer' object has no attribute '_owner' that a program may use: the fields of Pystachy's pyobj.Buffer are its own (its methods are not)
from pyobj import import_module, of_str

print(import_module("array").attr("array").call([of_str("d")]).buffer_f64()._owner)
