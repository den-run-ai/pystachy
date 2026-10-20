# error: tests/ffi/errors/c_at_local.py:10: error: local variable 'at' is read before its first assignment
from ffi import at, c_size_t, extern


@extern("libpystachy-ffitest.so")
def ffi_sum(x: list[float], n: c_size_t) -> float: ...


def g(xs: list[float]) -> float:
    r = ffi_sum(at(xs, 1), 1)
    at = 5
    return r + at


print(g([1.0, 2.0]))
