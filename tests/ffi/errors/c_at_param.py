# error: tests/ffi/errors/c_at_param.py:10: error: ffi.at() passes a list from an index, but parameter 'n' of ffi_scale() takes no list
from ffi import at, c_size_t, extern


@extern("libpystachy-ffitest.so")
def ffi_scale(x: list[float], n: c_size_t, k: float) -> None: ...


xs = [1.0, 2.0]
ffi_scale(xs, at(xs, 1), 2.0)
