# error: tests/ffi/errors/ctypes_mutation.py:8: error: ctypes declarations: prototypes are immutable
import ctypes

lib = ctypes.CDLL(None)
lib.abs.argtypes = [ctypes.c_int]
lib.abs.restype = ctypes.c_int
print(lib.abs(-1))
lib.abs.restype = ctypes.c_void_p
