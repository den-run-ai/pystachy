# UnicodeDecodeError(encoding, object, start, end, reason) and UnicodeEncodeError(...), made of
# CPython's five arguments: str() names the byte or character at start (\x, \u or \U escaped),
# or the range to end, also out of the object's bounds; repr(), catching them as UnicodeError and
# ValueError, exception values, and the uncaught exception's line
def dec(enc: str, b: bytes, s: int, e: int, why: str) -> None:
    try:
        raise UnicodeDecodeError(enc, b, s, e, why)
    except UnicodeDecodeError as x:
        print(x, "|", repr(x))


def enc(enc: str, t: str, s: int, e: int, why: str) -> None:
    try:
        raise UnicodeEncodeError(enc, t, s, e, why)
    except UnicodeError as x:
        print(x, "|", repr(x))


dec("charmap", b"\x81", 0, 1, "character maps to <undefined>")
dec("utf-8", b"ab\xff", 2, 3, "invalid start byte")
dec("utf-8", b"ab\xe2\x82", 2, 4, "unexpected end of data")
dec("x", b"abc", 5, 6, "out of range")
dec("x", b"abc", -1, 0, "negative")
dec("x", b"", 0, 0, "empty")
dec("x", b"abc", 1, 1, "empty range")
enc("charmap", "\x80", 0, 1, "character maps to <undefined>")
enc("ascii", "aé€😀", 1, 2, "ordinal not in range(128)")
enc("ascii", "aé€😀", 2, 3, "r")
enc("ascii", "aé€😀", 3, 4, "r")
enc("ascii", "aé€😀", 1, 4, "r")
enc("ascii", "a\udcff", 1, 2, "surrogates not allowed")
enc("latin-1", "abc", 7, 8, "far")
enc("latin-1", "", 0, 1, "nothing")
try:
    raise UnicodeDecodeError("utf-8", b"\xff", True, 2, "bools are ints")
except ValueError as x:
    print("ValueError:", x)
e = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
print(e, repr(e), isinstance(e, ValueError), isinstance(e, UnicodeError), isinstance(e, UnicodeEncodeError))
try:
    raise e
except UnicodeDecodeError as x:
    print("UnicodeDecodeError:", x)
raise UnicodeEncodeError("ascii", "é", 0, 1, "ordinal not in range(128)")
