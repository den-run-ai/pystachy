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


def integer(value: int | bool) -> None:
    print(lib.ffi_echo_int(value), lib.ffi_echo_uint(value), lib.ffi_echo_int64(value))


def number(value: int | float | bool) -> None:
    print(lib.ffi_echo_float(value), lib.ffi_echo_double(value))


def optional_address(value: int | None) -> None:
    cell = ct.c_void_p(value)
    print(lib.ffi_pointer_echo(value), cell.value, ct.string_at(value, 0))


def address(value: int | bool | None) -> None:
    cell = ct.c_void_p(value)
    print(lib.ffi_pointer_echo(value), cell.value, bool(cell))
    cell.value = value
    print(cell.value, ct.string_at(value, 0))


integers: list[int | bool] = [False, True, 0, -1, 2147483648, 4294967295, -(2**40) + 7]
for integer_value in integers:
    integer(integer_value)

numbers: list[int | float | bool] = [False, True, 7, -12, 0.125, -0.0, 16777217.0]
for number_value in numbers:
    number(number_value)

optional_addresses: list[int | None] = [None, 0, 7]
for optional_value in optional_addresses:
    optional_address(optional_value)

addresses: list[int | bool | None] = [None, False, True, 0, 7]
for address_value in addresses:
    address(address_value)
