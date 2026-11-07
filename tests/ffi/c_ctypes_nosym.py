# Lookup occurs on the first signature assignment, before a later library open.
import ctypes

lib = ctypes.CDLL("libm.so.6")
import side_noisy

lib.no_such_function_here.restype = ctypes.c_int
lib.no_such_function_here.argtypes = []
unused = ctypes.CDLL("libpystachy-no-such-library.so.9")

print("not reached")
