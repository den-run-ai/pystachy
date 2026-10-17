# error: tests/ffi/errors/c_list_cfloat.py:6: error: C function f() takes list[c_float]: C gets a list's items in place, 8 bytes each, as a double * (list[float]) or an int64_t * (list[ffi.c_int64]); copy them into the C type with a shim
from ffi import extern, c_float, c_size_t


@extern("")
def f(xs: list[c_float], n: c_size_t) -> c_float: ...


print(f([1.0], 1))
