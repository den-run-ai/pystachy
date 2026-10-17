# error: tests/ffi/errors/c_list_qualified_cfloat.py:6: error: C function f() takes list[ffi.c_float]: C gets a list's items in place, 8 bytes each, as a double * (list[float]) or an int64_t * (list[ffi.c_int64]); copy them into the C type with a shim
import ffi as c


@c.extern("")
def f(xs: list[c.c_float], n: c.c_size_t) -> c.c_float: ...


print(f([1.0], 1))
