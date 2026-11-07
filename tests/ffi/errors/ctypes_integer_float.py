# error: ctypes integer argument requires int | bool, got float
import ctypes as ct

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_echo_int.argtypes = [ct.c_int]
lib.ffi_echo_int.restype = ct.c_int
print(lib.ffi_echo_int(1.5))
