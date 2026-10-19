# ffi.at(xs, k) passes a list to an @extern function's list[float] or list[c_int64] parameter from
# its index k: C gets a pointer to item k of the list's own items, for the call, and may read and
# write the len(xs) - k items from there. k is checked when the call starts, once the other
# arguments are evaluated: 0 <= k <= len(xs), else IndexError. A list passed twice, from two
# indices, is one array (tools/rt_cpython too)
import ffi
from ffi import at, c_int64, c_size_t, extern


@extern("libpystachy-ffitest.so")
def ffi_sum(x: list[float], n: c_size_t) -> float: ...


@extern("libpystachy-ffitest.so")
def ffi_axpy(n: c_size_t, a: float, x: list[float], y: list[float]) -> None: ...


@extern("libpystachy-ffitest.so")
def ffi_scale(x: list[float], n: c_size_t, k: float) -> None: ...


@extern("libpystachy-ffitest.so")
def ffi_isum(x: list[c_int64], n: c_size_t) -> c_int64: ...


@extern("libpystachy-ffitest.so")
def ffi_iota(x: list[c_int64], n: c_size_t, start: c_int64) -> None: ...


def shrink(xs: list[float]) -> int:
    xs.pop()
    return 0


xs = [1.0, 2.0, 3.0, 4.0, 5.0]
print(ffi_sum(at(xs, 1), 3), ffi_sum(at(xs, 0), len(xs)), ffi_sum(ffi.at(xs, 4), 1), ffi_sum(at(xs, len(xs)), 0))
ffi_scale(at(xs, 2), 2, 10.0)  # (C writes the list's own items 2 and 3)
print(xs)
ffi_axpy(2, 1.0, at(xs, 0), at(xs, 3))  # (one array: items 3 and 4 get items 0 and 1 added)
print(xs, ffi_sum(n=2, x=at(xs, 3)))
ints = [0] * 6
ffi_iota(at(ints, 2), 3, 7)
print(ints, ffi_isum(at(ints, 1), 4), ffi_isum(at(ints, True), 1))
# a list built in the call, and a big one through collections (the tests run in stress mode)
print(ffi_sum(at([float(i) for i in range(10)], 7), 3))
big = [float(i) for i in range(100000)]
ffi_scale(at(big, 50000), 50000, 2.0)
print(big[49999], big[50000], big[99999], ffi_sum(at(big, 99998), 2))
for k in [-1, 6, -9223372036854775807 - 1]:
    try:
        ffi_sum(at(xs, k), 0)
    except IndexError as e:
        print("IndexError", e)
# the index is checked after the other arguments: shrink() takes xs's last item first
ys = [1.0, 2.0, 3.0, 4.0]
print(ffi_sum(at(ys, 3), shrink(ys)), ys)
try:
    ffi_sum(at(ys, 3), shrink(ys))
except IndexError as e:
    print("IndexError", e, ys)
