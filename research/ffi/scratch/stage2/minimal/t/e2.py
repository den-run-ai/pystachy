from ffi import extern


@extern("")
def abs(x: int) -> None: ...


try:
    abs(1)
except ValueError:
    print(1)
