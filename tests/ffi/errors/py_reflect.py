# error: tests/ffi/errors/py_reflect.py:4: error: reflection of a pyobj.Object object is not supported: its fields are Pystachy's pyobj module's own (its twin's are others), and a program may use only its methods
from pyobj import of_int

print(dir(of_int(7)))
