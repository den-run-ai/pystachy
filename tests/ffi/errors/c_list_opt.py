# error: tests/ffi/errors/c_list_opt.py:6: error: C function f() takes list[float] | None: an @extern function takes a C integer type, float, str, list[float] or list[ffi.c_int64]
from ffi import extern, c_size_t


@extern("")
def f(xs: list[float] | None, n: c_size_t) -> float: ...


print(f(None, 0))
