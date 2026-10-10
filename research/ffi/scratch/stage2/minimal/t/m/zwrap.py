from ffi import extern


@extern("libz.so.1")
def zlibVersion() -> str: ...


@extern("libz.so.1", "adler32")
def _adler32(adler: int, buf: str, n: int) -> int: ...


def adler32(s: str) -> int:
    return _adler32(1, s, len(s)) & 0xFFFFFFFF
