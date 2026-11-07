# error: tests/ffi/errors/ctypes_private_symbol.py:5: error: ctypes declarations: private CDLL attributes are not foreign symbol declarations
import ctypes

lib = ctypes.CDLL(None)
lib._handle.argtypes = []
lib._handle.restype = ctypes.c_void_p
