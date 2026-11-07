# error: ctypes number argument requires int | bool | float, got str
import ctypes as ct

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_echo_double.argtypes = [ct.c_double]
lib.ffi_echo_double.restype = ct.c_double
print(lib.ffi_echo_double("1.5"))
