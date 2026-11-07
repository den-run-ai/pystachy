# error: tests/ffi/errors/ctypes_escape.py:8: error: ctypes declarations: libraries and foreign function objects cannot escape or be rebound
import ctypes

lib = ctypes.CDLL(None)
lib.abs.argtypes = [ctypes.c_int]
lib.abs.restype = ctypes.c_int

function = lib.abs
