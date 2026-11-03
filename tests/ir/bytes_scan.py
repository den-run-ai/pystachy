# The shipped helper lowers to a reusable scan of byte spans, with either generic
# delimiters or JSON's control threshold. Public JSON tests cover its consumers.
from _pystachy_bytescan import scan


def delimiters(data: bytes, start: int, end: int) -> int:
    return scan(data, start, end, 44, 59, 0)


def controls(data: bytes, start: int, end: int) -> int:
    return scan(data, start, end, 34, 92, 32)


print(delimiters(b"abcdefgh;rest", 0, 13), controls(b"abcdefgh\\rest", 0, 13))
