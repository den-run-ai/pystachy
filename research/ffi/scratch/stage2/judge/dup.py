from ffi import extern, c_int


@extern("", "abs")
def abs1(n: int) -> int: ...


@extern("", "abs")
def abs2(n: c_int) -> c_int: ...


@extern("")
def memchr(p: str, c: int, n: int) -> int: ...


@extern("")
def pys_len(x: int) -> int: ...


print(abs1(-5), abs2(-5))
print(memchr("abc", 98, 3) != 0)
