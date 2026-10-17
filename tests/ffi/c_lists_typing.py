# typing.List spells the same borrowed arrays as list in both the compiler and CPython twin.
from typing import List
from ffi import c_int64, c_size_t, c_ssize_t, extern


@extern("libpystachy-ffitest.so")
def ffi_sum(x: List[float], n: c_size_t) -> float: ...


@extern("libpystachy-ffitest.so")
def ffi_iota(x: List[c_int64], n: c_size_t, start: c_int64) -> None: ...


@extern("libpystachy-ffitest.so")
def ffi_isum(x: List[c_ssize_t], n: c_size_t) -> c_int64: ...


xs = [0] * 3
ffi_iota(xs, len(xs), -1)
print(ffi_sum([1.0, 2.0], 2), xs, ffi_isum(xs, len(xs)))
