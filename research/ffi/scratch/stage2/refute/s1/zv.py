from ffi import extern


@extern("")
def zlibVersion() -> str: ...


print(zlibVersion()[:2])
