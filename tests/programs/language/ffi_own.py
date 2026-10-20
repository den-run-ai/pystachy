# A program's own ffi module (tests/ownffi/ffi.py, on the module path) comes first, as under
# CPython: none of the names of Pystachy's builtin ffi module means what it means there
import ffi
from ffi import extern, export, c_int, string_at


def f(n: int) -> int:
    return extern(n) + export(n)


print(ffi.extern(41), f(4), c_int, string_at(3, 2), ffi.track(5, 2), ffi.collected())
ffi.untrack(9)
print(ffi.string_at(12, 3), ffi.c_int + 1)
