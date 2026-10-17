# @ffi.extern takes a list[float] as a double * and a list[c_int64] as an int64_t *: the list's own
# items, for the call, which C reads and writes in place (the length goes as another argument).
# tools/rt_cpython copies each distinct list into one C array and back, so a list passed for two
# parameters is one array in both runtimes: ffi_reverse(zs, zs, n) reads what it wrote.
from ffi import c_int64, c_size_t, extern


@extern("libpystachy-ffitest.so")
def ffi_sum(x: list[float], n: c_size_t) -> float: ...


@extern("libpystachy-ffitest.so")
def ffi_axpy(n: c_size_t, a: float, x: list[float], y: list[float]) -> None: ...


@extern("libpystachy-ffitest.so")
def ffi_scale(x: list[float], n: c_size_t, k: float) -> None: ...


@extern("libpystachy-ffitest.so")
def ffi_reverse(x: list[float], y: list[float], n: c_size_t) -> None: ...


@extern("libpystachy-ffitest.so")
def ffi_isum(x: list[c_int64], n: c_size_t) -> c_int64: ...


@extern("libpystachy-ffitest.so")
def ffi_iota(x: list[c_int64], n: c_size_t, start: c_int64) -> None: ...


xs = [1.0, 2.0, 3.0, 4.0]
empty: list[float] = []
print(ffi_sum(xs, len(xs)), ffi_sum(empty, 0))
ys = [10.0, 20.0, 30.0, 40.0]
ffi_axpy(len(xs), 2.0, xs, ys)
print(ys, xs)
ffi_scale(xs, 2, -1.0)  # (only the first two items)
print(xs)
ffi_axpy(len(xs), 2.0, xs, xs)  # (y += 2 * x, x and y one array: each item tripled)
print(xs)
zs = [1.0, 2.0, 3.0, 4.0]
ffi_reverse(zs, zs, len(zs))  # (one array: the second half reads the first half reversed)
ws = [1.0, 2.0, 3.0, 4.0]
out = [0.0] * 4
ffi_reverse(ws, out, len(ws))
print(zs, out, ws)
# the bits of a float pass as they are, both ways
sp = [-0.0, float("inf"), float("-inf"), float("nan"), 5e-324, 1.7976931348623157e308]
ffi_scale(sp, len(sp), 1.0)
print(sp)
# the items after the list grew, and through collections around the calls (the tests run with
# the collector in stress mode)
grown: list[float] = []
for i in range(1000):
    grown.append(i * 0.5)
print(ffi_sum(grown, len(grown)), ffi_sum(grown, 10))
big = [float(i) for i in range(100000)]
ffi_scale(big, len(big), 2.0)
print(ffi_sum(big, len(big)), big[99999])
# a slice is a new list: C writes it, not the list it came from
q = [1.0, 2.0, 3.0]
part = q[1:]
ffi_scale(part, len(part), 10.0)
print(q, part)
grown.clear()
print(ffi_sum(grown, 0), grown)
ints = [0] * 5
ffi_iota(ints, len(ints), -2)
print(ints, ffi_isum(ints, len(ints)), ffi_isum([2**62, 2**62 - 1, -(2**62)], 3))
