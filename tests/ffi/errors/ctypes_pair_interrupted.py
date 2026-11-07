# error: tests/ffi/errors/ctypes_pair_interrupted.py:6: error: ctypes declarations: complete each argtypes/restype pair before any other declaration or execution
import ctypes

lib = ctypes.CDLL(None)
lib.abs.argtypes = [ctypes.c_int]
import side_noisy
lib.abs.restype = ctypes.c_int
