# pystachy: python-int
import ctypes as ct

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_echo_int.argtypes = [ct.c_int]
lib.ffi_echo_int.restype = ct.c_int
lib.ffi_echo_uint.argtypes = [ct.c_uint]
lib.ffi_echo_uint.restype = ct.c_uint
lib.ffi_echo_int64.argtypes = [ct.c_int64]
lib.ffi_echo_int64.restype = ct.c_int64
lib.ffi_echo_double.argtypes = [ct.c_double]
lib.ffi_echo_double.restype = ct.c_double
lib.ffi_pointer_echo.argtypes = [ct.c_void_p]
lib.ffi_pointer_echo.restype = ct.c_void_p


def integer(value: int) -> None:
    print(lib.ffi_echo_int(value), lib.ffi_echo_uint(value), lib.ffi_echo_int64(value))
    print(lib.ffi_echo_double(value))


def address(value: int) -> None:
    cell = ct.c_void_p(value)
    print(lib.ffi_pointer_echo(value), cell.value, ct.string_at(value, 0))


wide = 2**80
integer(wide - wide + 4294967295)
integer(-(2**40) + 7)
integer(-9223372036854775808)
integer(9223372036854775807)
address(wide - wide)
address(wide - wide + 7)
