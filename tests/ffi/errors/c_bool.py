# error: tests/ffi/errors/c_bool.py:6: error: C function f() takes bool: an @extern function takes a C integer type, float, str, list[float] or list[ffi.c_int64]
from ffi import extern, c_int


@extern("")
def f(b: bool) -> c_int: ...


print(f(True))
