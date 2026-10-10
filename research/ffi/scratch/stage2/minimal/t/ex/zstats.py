from ffi import extern, c_int, string_at


@extern("libz.so.1")
def zlibVersion() -> str: ...


@extern("libz.so.1")
def adler32(adler: int, buf: str, n: c_int) -> int: ...


@extern("")  # libc: already in the process
def strdup(s: str) -> int: ...


@extern("")
def free(p: int) -> None: ...


p = strdup("Wikipedia")
s = string_at(p, 9)
free(p)
print(zlibVersion()[:2], s, adler32(1, s, len(s)))
