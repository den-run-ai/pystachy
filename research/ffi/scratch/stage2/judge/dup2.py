from ffi import extern


@extern("")
def memchr(p: str, c: int, n: int) -> int: ...


print(memchr("abc", 98, 3) != 0, "abc".find("b"))
