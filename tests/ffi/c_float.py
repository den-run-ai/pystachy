# ffi.c_float: a C float, 32 bits. An argument is rounded to the nearest float, as ctypes rounds it
# (ties to even, an infinity past the largest float), and a result is widened to a float exactly
from ffi import c_float, extern


@extern("libm.so.6")
def sqrtf(x: c_float) -> c_float: ...


@extern("libm.so.6")
def nextafterf(x: c_float, y: c_float) -> c_float: ...


@extern("libpystachy-ffitest.so")
def ffi_widen(x: c_float) -> float: ...


@extern("libpystachy-ffitest.so")
def ffi_narrow(x: float) -> c_float: ...


@extern("libpystachy-ffitest.so")
def ffi_fmul(a: c_float, b: c_float) -> c_float: ...


print(sqrtf(2.0), sqrtf(-0.0), nextafterf(1.0, 2.0) - 1.0, sqrtf(-1.0))
print(ffi_widen(0.1), ffi_narrow(0.1), ffi_fmul(1.5, 2.0), ffi_fmul(0.1, 3.0))
print(ffi_widen(1e40), ffi_widen(-1e40), ffi_widen(1e-46), ffi_widen(-1e-46), ffi_widen(float("inf")), ffi_widen(float("nan")))
# ties to even: 1 + 2**-24 lies halfway between 1.0 and the next float, 1 + 3 * 2**-24 between that
# and the one after, and 2**24 + 1 between two integers
print(ffi_widen(1.0 + 2.0**-24), ffi_widen(1.0 + 3 * 2.0**-24), ffi_narrow(16777217.0), ffi_narrow(3.4028235677973366e38))
