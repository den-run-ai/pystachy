# error: tests/ffi/errors/ctypes_incomplete.py:5: error: ctypes declarations: every foreign function needs explicit argtypes and restype
import ctypes

lib = ctypes.CDLL(None)
lib.abs.argtypes = [ctypes.c_int]

print(lib.abs(-1))
