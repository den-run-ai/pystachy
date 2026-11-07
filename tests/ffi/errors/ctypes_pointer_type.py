# error: tests/ffi/errors/ctypes_pointer_type.py:5: error: ctypes declarations: unsupported C type
import ctypes

lib = ctypes.CDLL(None)
lib.f.argtypes = [ctypes.POINTER(ctypes.c_int)]
lib.f.restype = None
