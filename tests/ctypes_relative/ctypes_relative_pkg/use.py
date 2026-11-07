from .ctypes import api as ct

lib = ct.CDLL(None)
lib.abs.argtypes = [ct.c_int]
lib.abs.restype = ct.c_int

print(lib.abs(-7))
