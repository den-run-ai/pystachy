from ffi import extern, c_int, c_uint


@extern("z")
def crc32(crc: int, buf: bytes, n: c_uint) -> int: ...


@extern("m")
def cbrt(x: float) -> float: ...


@extern("c")
def strcmp(a: str, b: str) -> c_int: ...


data = b"hello world"
print(crc32(0, data, len(data)))
print(cbrt(27.0))
print(strcmp("a", "b"))
