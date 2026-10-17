# error: tests/ffi/errors/c_python.py:6: error: @extern("python") is reserved for Pystachy's lib/pyobj.py: import pyobj to call CPython
from ffi import extern, c_int


@extern("python")
def Py_IsInitialized() -> c_int: ...


print(Py_IsInitialized())
