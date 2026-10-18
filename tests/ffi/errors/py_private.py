# error: tests/ffi/errors/py_private.py:2: error: cannot import name 'PyLong_AsLongLong' from 'pyobj': Pystachy's pyobj module offers Object, import_module, of_int, of_float, of_str, of_list (as its twin, tools/rt_cpython/pyobj.py, does)
from pyobj import of_int, PyLong_AsLongLong

print(PyLong_AsLongLong(0), of_int(1))
