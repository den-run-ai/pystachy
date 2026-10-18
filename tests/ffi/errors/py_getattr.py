# error: tests/ffi/errors/py_getattr.py:4: error: hasattr() or getattr() with a default of a pyobj.Object object is not supported: its fields are Pystachy's pyobj module's own (its twin's are others), and a program may use only its methods
from pyobj import of_int

print(getattr(of_int(7), "close", None))
