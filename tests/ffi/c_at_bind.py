# ffi.at is bound as any imported name is: a call that runs before its import, or where the import
# did not run, raises NameError, as under CPython, and calls no C function. The index of an
# IndexError reads as an int in both runtimes, also when the program gives a bool
import sys

from ffi import c_size_t, extern

if len(sys.argv) > 5:
    import ffi as F


@extern("libpystachy-ffitest.so")
def ffi_sum(x: list[float], n: c_size_t) -> float: ...


def early(xs: list[float]) -> float:
    return ffi_sum(at(xs, 1), 1)


xs = [1.0, 2.0]
try:
    print(early(xs))
except NameError as e:
    print("NameError", e)
try:
    print(ffi_sum(F.at(xs, 1), 1))
except NameError as e:
    print("NameError", e)
from ffi import at  # noqa: E402

print(early(xs))
empty: list[float] = []
try:
    print(ffi_sum(at(empty, True), 0))
except IndexError as e:
    print("IndexError", e)
