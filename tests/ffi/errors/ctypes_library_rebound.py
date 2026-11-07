# error: tests/ffi/errors/ctypes_library_rebound.py:4: error: ctypes declarations: assign CDLL to one fresh module name
import ctypes

lib = ctypes.CDLL(None)
lib.abs.argtypes = [ctypes.c_int]
lib.abs.restype = ctypes.c_int

lib = replacement
