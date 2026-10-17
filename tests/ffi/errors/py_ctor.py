# error: tests/ffi/errors/py_ctor.py:4: error: pyobj.Object() cannot be called: Pystachy's pyobj module makes its objects (with import_module, of_int, of_float, of_str, of_list)
from pyobj import Object

x = Object(5, 0)
print(x)
