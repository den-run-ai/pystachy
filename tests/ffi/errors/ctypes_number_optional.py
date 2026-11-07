# error: ctypes number argument requires int | bool | float, got int | None
import ctypes as ct

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_echo_double.argtypes = [ct.c_double]
lib.ffi_echo_double.restype = ct.c_double


def number(value: int | None) -> float:
    return lib.ffi_echo_double(value)


print(number(None))
