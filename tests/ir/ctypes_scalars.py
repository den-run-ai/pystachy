# Concrete ctypes arguments must reach the native ABI without union boxes.
# The calls contract covers conversion helpers as well as their callers, so
# moving an allocation into a generated wrapper cannot hide a regression.
import ctypes as ct

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_echo_int.argtypes = [ct.c_int]
lib.ffi_echo_int.restype = ct.c_int
lib.ffi_echo_uint.argtypes = [ct.c_uint]
lib.ffi_echo_uint.restype = ct.c_uint
lib.ffi_echo_int64.argtypes = [ct.c_int64]
lib.ffi_echo_int64.restype = ct.c_int64
lib.ffi_echo_float.argtypes = [ct.c_float]
lib.ffi_echo_float.restype = ct.c_float
lib.ffi_echo_double.argtypes = [ct.c_double]
lib.ffi_echo_double.restype = ct.c_double
lib.ffi_pointer_echo.argtypes = [ct.c_void_p]
lib.ffi_pointer_echo.restype = ct.c_void_p


def integers(value: int, flag: bool) -> int:
    return lib.ffi_echo_int(value) + lib.ffi_echo_uint(value) + lib.ffi_echo_int64(flag)


def floating(value: float, integer: int, flag: bool) -> float:
    return lib.ffi_echo_float(value) + lib.ffi_echo_double(integer) + lib.ffi_echo_double(flag)


def pointer(value: int) -> int | None:
    return lib.ffi_pointer_echo(value)


print(integers(-1, True), floating(1.25, 2, False), pointer(0))
