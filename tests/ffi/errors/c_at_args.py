# error: tests/ffi/errors/c_at_args.py:10: error: ffi.at() takes a list and an index: ffi.at(xs, k)
from ffi import at, c_size_t, extern


@extern("libpystachy-ffitest.so")
def ffi_sum(x: list[float], n: c_size_t) -> float: ...


xs = [1.0, 2.0]
print(ffi_sum(at(xs), 1))
