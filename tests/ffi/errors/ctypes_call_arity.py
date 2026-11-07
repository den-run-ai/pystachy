# error: tests/ffi/errors/ctypes_call_arity.py:8: error: ctypes declarations: foreign calls require exactly the declared positional arguments
import ctypes

lib = ctypes.CDLL(None)
lib.abs.argtypes = [ctypes.c_int]
lib.abs.restype = ctypes.c_int

print(lib.abs(-1, -2))
