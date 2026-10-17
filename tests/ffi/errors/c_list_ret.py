# error: tests/ffi/errors/c_list_ret.py:6: error: C function f() returns list[float]: an @extern function returns a C integer type, float or str, str | None or None
from ffi import extern, c_size_t


@extern("")
def f(n: c_size_t) -> list[float]: ...


print(f(1))
