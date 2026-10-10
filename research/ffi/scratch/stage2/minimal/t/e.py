from ffi import extern


@extern("")
def f(x: bool) -> int: ...


print(f(True))
