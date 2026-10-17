# py_samesym.py's: a C function of libpython that lib/pyobj.py declares too
from ffi import extern, c_int


@extern("")
def Py_IsInitialized() -> c_int: ...
