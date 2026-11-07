# pystachy: dynamic-any
import ctypes as ct
from typing import Any

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_echo_int.argtypes = [ct.c_int]
lib.ffi_echo_int.restype = ct.c_int
lib.ffi_echo_double.argtypes = [ct.c_double]
lib.ffi_echo_double.restype = ct.c_double
lib.ffi_pointer_echo.argtypes = [ct.c_void_p]
lib.ffi_pointer_echo.restype = ct.c_void_p
lib.ffi_fmul.argtypes = [ct.c_float, ct.c_float]
lib.ffi_fmul.restype = ct.c_float


def first() -> Any:
    print("first")
    return "1.25"


def second() -> Any:
    print("second")
    return 0.5


integers: list[Any] = [False, True, 0, -1, 4294967295]
for integer_value in integers:
    print(lib.ffi_echo_int(integer_value))
numbers: list[Any] = [False, True, 7, 0.125, -0.0]
for number_value in numbers:
    print(lib.ffi_echo_double(number_value))
addresses: list[Any] = [None, False, True, 0, 7]
for address_value in addresses:
    print(lib.ffi_pointer_echo(address_value), ct.string_at(address_value, 0))

# Argument expressions finish before the wrapper converts the first argument.
try:
    lib.ffi_fmul(first(), second())
except Exception:
    print("rejected")
