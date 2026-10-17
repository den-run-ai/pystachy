# Qualified C types retain their ABI widths, including module aliases and quoted annotations.
import ffi
import ffi as c


@ffi.extern("libc.so.6")
def abs(x: ffi.c_int) -> ffi.c_int: ...


@c.extern("libm.so.6")
def sqrtf(x: c.c_float) -> c.c_float: ...


@ffi.extern("libpystachy-ffitest.so")
def ffi_widen(x: "ffi.c_float") -> float: ...


@c.extern("libc.so.6")
def strnlen(x: c.c_buf, n: c.c_size_t) -> c.c_size_t: ...


@ffi.extern("libpystachy-ffitest.so")
def ffi_iota(x: list[ffi.c_int64], n: ffi.c_size_t, start: ffi.c_int64) -> None: ...


@c.extern("libpystachy-ffitest.so")
def ffi_isum(x: "list[c.c_ssize_t]", n: c.c_size_t) -> c.c_int64: ...


xs = [0] * 3
ffi_iota(xs, len(xs), -1)
print(abs(-3), sqrtf(4.0), ffi_widen(0.1), strnlen("ab\0cd", 5))
print(xs, ffi_isum(xs, len(xs)))
