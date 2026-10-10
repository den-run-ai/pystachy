from ffi import extern, c_void_p, c_size_t, string_at


@extern("")
def getenv(name: str) -> str | None: ...


@extern("")
def strlen(s: c_void_p) -> c_size_t: ...


v = getenv("PYS_T")
if v is not None:
    print(len(v), v == "caf\xe9")
