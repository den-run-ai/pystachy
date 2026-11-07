# error: tests/ffi/errors/py_buffer_ctor.py:4: error: pyobj.Buffer() cannot be called: Pystachy's pyobj module makes its objects (with Object, import_module, of_int, of_float, of_str, of_list)
from pyobj import Buffer, of_int

b = Buffer(of_int(0))
