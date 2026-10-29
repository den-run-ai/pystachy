# pystachy: python-int
# A list[c_int64] parameter takes a list of ints whose items fit in 64 bits; one that holds an int
# past 64 bits raises OverflowError before C reads it, directly and through ffi.at(), and C's
# writes are the list's ints afterwards (also -2**63, which marks an item past 64 bits). ffi.at()
# takes a promoting int as its index.
from ffi import at, c_int64, c_size_t, extern


@extern("libpystachy-ffitest.so")
def ffi_isum(x: list[c_int64], n: c_size_t) -> c_int64: ...


@extern("libpystachy-ffitest.so")
def ffi_iota(x: list[c_int64], n: c_size_t, start: c_int64) -> None: ...


xs = [1, 2, 3]
print(ffi_isum(xs, len(xs)), ffi_isum(at(xs, 2 ** 64 - 2 ** 64 + 1), 2))
ys = [2 ** 64, 1]
try:
    print(ffi_isum(ys, len(ys)))
except OverflowError:
    print("OverflowError")
try:
    print(ffi_isum(at(ys, 0), len(ys)))
except OverflowError:
    print("OverflowError at()")
try:
    ffi_iota(ys, len(ys), 5)
except OverflowError:
    print("OverflowError iota")
print(ys)
ys[0] = 4
ffi_iota(ys, len(ys), -2 ** 63)
print(ys, ys[0] == -2 ** 63, ys[1] - 1)
ys.append(-(2 ** 70))
print(ys)
try:
    print(ffi_isum(ys, 1))
except OverflowError:
    print("OverflowError after append")
ys.pop()
print(ffi_isum(ys, 1), ys)
