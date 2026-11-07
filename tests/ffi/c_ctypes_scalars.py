# Compare the static ctypes declarations with CPython's real ctypes conversions.
import ctypes as ct

lib = ct.CDLL("libpystachy-ffitest.so")
lib.ffi_echo_int.argtypes = [ct.c_int]
lib.ffi_echo_int.restype = ct.c_int
lib.ffi_echo_uint.argtypes = [ct.c_uint]
lib.ffi_echo_uint.restype = ct.c_uint
lib.ffi_echo_int64.argtypes = [ct.c_int64]
lib.ffi_echo_int64.restype = ct.c_longlong
lib.ffi_echo_float.argtypes = [ct.c_float]
lib.ffi_echo_float.restype = ct.c_float
lib.ffi_echo_double.argtypes = [ct.c_double]
lib.ffi_echo_double.restype = ct.c_double
process = ct.CDLL(None)
process.abs.argtypes = [ct.c_int32]
process.abs.restype = ct.c_int32

for integer in [0, 2147483647, 2147483648, 4294967295, 4294967296, -1, -2147483649, -(2**40) + 7]:
    print(lib.ffi_echo_int(integer), lib.ffi_echo_uint(integer))
print(lib.ffi_echo_int(True), lib.ffi_echo_uint(False), process.abs(4294967295))
for wide in [-9223372036854775808, -(2**60) - 3, 2**60 + 3, 9223372036854775807]:
    print(lib.ffi_echo_int64(wide))
for floating in [0.1, 16777217.0, -0.0, 1e40, -1e40]:
    print(lib.ffi_echo_float(floating), lib.ffi_echo_double(floating))
print(lib.ffi_echo_float(float("inf")), lib.ffi_echo_float(float("nan")))
print(lib.ffi_echo_int64(True), lib.ffi_echo_float(True), lib.ffi_echo_double(False),
      lib.ffi_echo_float(3), lib.ffi_echo_double(4))
