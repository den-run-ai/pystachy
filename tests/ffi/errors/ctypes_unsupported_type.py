# error: tests/ffi/errors/ctypes_unsupported_type.py:5: error: ctypes declarations: unsupported C type
import ctypes

lib = ctypes.CDLL(None)
lib.abs.argtypes = [ctypes.c_bool]
lib.abs.restype = ctypes.c_int
