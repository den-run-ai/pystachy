# @ffi.extern: C functions of the C library (""), with each C integer's width named
from ffi import extern, string_at, c_int, c_int64, c_uint64, c_size_t, c_void_p, c_buf


@extern("")
def strdup(s: str) -> c_void_p: ...


@extern("")
def free(p: c_void_p) -> None: ...


@extern("")
def strlen(s: str) -> c_size_t: ...


@extern("")
def strnlen(s: c_buf, n: c_size_t) -> c_size_t: ...


@extern("")
def strcmp(a: str, b: str) -> c_int: ...


@extern("")
def atoi(s: str) -> c_int: ...


@extern("")
def abs(n: c_int) -> c_int: ...


@extern("")
def labs(n: c_int64) -> c_int64: ...


@extern("", "strtoull")
def to_u64(s: str, end: c_void_p, base: c_int) -> c_uint64: ...


@extern("")
def getenv(name: str) -> str | None: ...


@extern("")
def memchr(s: str, c: c_int, n: c_size_t) -> c_void_p: ...  # (the runtime's own, with the same types)


# the library and the symbol by keyword, as the twin's extern(lib, symbol="") takes them, and an empty
# symbol for the function's own name
@extern("", symbol="atol")
def to_long(s: str) -> c_int64: ...


@extern(lib="", symbol="toupper")
def upper(c: c_int) -> c_int: ...


@extern("", symbol="abs")
def c_abs(n: c_int) -> c_int: ...  # (abs again, with the same types)


@extern("", "")
def strncmp(a: str, b: str, n: c_size_t) -> c_int: ...


p = strdup("Wikipedia")
s = string_at(p, strlen("Wikipedia"))
free(p)
# C guarantees only strcmp's sign; optimized libc implementations can return
# different magnitudes (for example -1/+1 on x86-64 and -64/+64 on AArch64).
print(s, strlen(s), strnlen("a\0b", 3), strcmp("a", "b") < 0, strcmp("b", "a") > 0, atoi("-5"), abs(-7), labs(-2**62))
print(to_u64("9223372036854775807", 0, 10), getenv("PYSTACHY_FFI_TEST_UNSET"), memchr("abc", 98, 3) != 0, "abc".find("b"))
# a dict key (made at run time, or a literal) caches its hash in the str, beside its bytes: C still
# gets only the bytes
d = {s: 1, "-12": 2}
print(strlen(s), atoi("-12"), strcmp(s, "Wikipedia"), strnlen(s, 99), d[s] + d["-12"])
print(to_long("-123456789012"), upper(97), c_abs(-9), strncmp("abcd", "abce", 3), strncmp("abcd", "abce", 4) < 0)
for k in range(6):
    try:
        if k == 0:
            print(abs(2**31))
        elif k == 1:
            print(strlen("a\0b"))
        elif k == 2:
            print(to_u64("18446744073709551615", 0, 10))
        elif k == 3:
            print(strnlen("ab", -1))
        elif k == 4:
            print(string_at(0, -1))
        else:
            print(abs(-2**31 - 1))
    except (OverflowError, ValueError) as e:
        print(type(e).__name__, e)
