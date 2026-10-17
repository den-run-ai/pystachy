# error: tests/ffi/errors/c_list.py:6: error: C function f() takes list[int]: say which C integer type its items are (list[ffi.c_int64], which C gets as an int64_t *)
from ffi import extern, c_int


@extern("")
def f(xs: list[int]) -> c_int: ...


print(f([1]))
