# error: tests/ffi/errors/c_at_value.py:5: error: ffi.at(xs, k) passes a list from an index to C: it is only an argument of a call of an @extern function, for a list[float] or list[ffi.c_int64] parameter
from ffi import at

xs = [1.0, 2.0]
ys = at(xs, 1)
print(ys)
