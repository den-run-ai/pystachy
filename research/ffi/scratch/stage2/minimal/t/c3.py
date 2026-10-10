from ffi import extern, c_int


@extern("")
def abs(x: c_int) -> c_int: ...


@extern("")
def strcmp(a: str, b: str) -> c_int: ...


@extern("")
def atoi(s: str) -> c_int: ...


print(abs(-5), strcmp("a", "b") < 0, strcmp("b", "a") > 0, atoi("-42"))
