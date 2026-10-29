# pystachy: dynamic-any
# The CPython ffi twin copies the entire list back even after a read-only C call.
# The list stays the same object; each numeric item has the copied-back identity.
from typing import Any
from ffi import at, c_int64, c_size_t, extern


@extern("libpystachy-ffitest.so")
def ffi_sum(x: list[float], n: c_size_t) -> float: ...


@extern("libpystachy-ffitest.so")
def ffi_scale(x: list[float], n: c_size_t, k: float) -> None: ...


@extern("libpystachy-ffitest.so")
def ffi_reverse(x: list[float], y: list[float], n: c_size_t) -> None: ...


@extern("libpystachy-ffitest.so")
def ffi_isum(x: list[c_int64], n: c_size_t) -> c_int64: ...


def same(a: Any, b: Any) -> bool:
    return a is b


nan: Any = float("nan")
xs: list[float] = [nan, nan, 2.0]
alias = xs
before = xs.copy()
seen: set[Any] = {xs[0], xs[1]}
print("before", xs[0] is nan, same(xs[0], xs[1]), len(seen))
ffi_sum(xs, 0)
print("readonly", alias is xs, xs[0] is nan, same(xs[0], before[0]), same(xs[0], xs[1]))
seen = {xs[0], xs[0], xs[1]}
print("stable", same(xs[0], xs[0]), same(xs[1], xs[1]), len(seen))
after = xs.copy()
print("copy", same(after[0], xs[0]), same(after[1], xs[1]))
ffi_scale(at(xs, 2), 1, 3.0)
print("offset", same(xs[0], after[0]), xs[2], same(xs[2], xs[2]))
ys = [1.0, 2.0, 3.0, 4.0]
old = ys.copy()
ffi_reverse(ys, ys, len(ys))
print("alias", ys, same(ys[0], old[3]), same(ys[0], ys[3]), same(ys[1], ys[2]))
print("alias stable", same(ys[0], ys[0]), same(ys[3], ys[3]))
value: Any = int("1000")
ints: list[int] = [value, value]
print("integer before", ints[0] is value, same(ints[0], ints[1]))
print("sum", ffi_isum(ints, len(ints)))
print("integer after", ints[0] is value, same(ints[0], ints[1]), same(ints[0], ints[0]))
