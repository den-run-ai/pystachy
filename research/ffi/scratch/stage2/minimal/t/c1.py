from ffi import extern


@extern("libm.so.6")
def cbrt(x: float) -> float: ...


@extern("")
def strlen(s: str) -> int: ...


@extern("")
def getenv(name: str) -> str | None: ...


print(cbrt(27.0))
print(strlen("héllo"))
print(getenv("NO_SUCH_VAR_X") is None)
