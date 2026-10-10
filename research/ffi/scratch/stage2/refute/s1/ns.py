from ffi import extern


@extern("")
def no_such_fn() -> None: ...


print("start")
no_such_fn()
