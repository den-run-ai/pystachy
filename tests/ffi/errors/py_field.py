# error: tests/ffi/errors/py_field.py:4: error: 'Object' object has no attribute '_p' that a program may use: the fields of Pystachy's pyobj.Object are its own (its methods are not)
from pyobj import of_int

print(of_int(7)._p != 0)
