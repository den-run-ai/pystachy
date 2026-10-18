# error: tests/ffi/errors/py_hasattr.py:4: error: hasattr() of a pyobj.Object object is not supported: its fields are Pystachy's pyobj module's own (its twin's are others), and a program may use only its methods
from pyobj import of_int

print(hasattr(of_int(7), "_p"))
