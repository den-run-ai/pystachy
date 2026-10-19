# error: tests/ffi/errors/c_at_index.py:10: error: ffi.at() takes an int index, not float
from ffi import at, c_size_t, extern


@extern("libpystachy-ffitest.so")
def ffi_sum(x: list[float], n: c_size_t) -> float: ...


xs = [1.0, 2.0]
print(ffi_sum(at(xs, 1.5), 1))
