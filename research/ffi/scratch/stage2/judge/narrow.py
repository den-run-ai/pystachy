from ffi import extern


@extern("")
def atoi(s: str) -> int: ...


print(atoi("-5"))
