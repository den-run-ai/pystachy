from zwrap import zlibVersion, adler32
from ffi import extern, string_at


@extern("")
def strtol(s: str, end: int, base: int) -> int: ...


@extern("")
def strdup(s: str) -> int: ...


@extern("")
def free(p: int) -> None: ...


print(zlibVersion()[:2])
for w in ["Wikipedia", "héllo", "x" * 1000]:
    print(adler32(w))
print(strtol("ff", 0, 16))
total = 0
for i in range(20000):
    s = "item " + str(i)
    p = strdup(s)
    total += len(string_at(p, len(s)))
    free(p)
print(total)
