# error: tests/ffi/errors/c_list_str.py:6: error: C function f() takes list[str]: an @extern function takes a C integer type, float, str, list[float] or list[ffi.c_int64]
from ffi import extern, c_size_t


@extern("")
def f(xs: list[str], n: c_size_t) -> c_size_t: ...


print(f(["a"], 1))
