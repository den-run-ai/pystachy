# bytes: literals (escapes, raw, adjacent), len, indexing (an int) and slicing, iteration over
# ints, +, *, comparisons, in, truth, repr() and printing, dict keys and set elements, bytes |
# None, parameters and returns, containers of bytes, IndexError, and bytes() of a range, a
# generator expression, map() and reversed()
b = b"hello"
e = b""
print(b, e, len(b), len(e))
print(b[0], b[-1], b[1:3], b[::-1], b[:0], b[1:], b[::2])
for x in b:
    print(x, end=" ")
print()
print([x for x in b], list(b))
print(b + b" world", b * 2, 3 * b"ab", b * 0)
print(b == b"hello", b != b"hello", b < b"help", b"a" <= b"a", b"b" > b"a", b >= b"hello", b"\xff" > b"a")
print(b"ell" in b, b"xyz" in b, 104 in b, 0 in b, b"" in b)
print(bool(b), bool(e), not e)
if b:
    print("truthy")
print(repr(b), str(b), f"{b}", f"{b!r}")
print(repr(b"\x00\x7f\x80\xff\t\n\r\\'\""), repr(b"it's"), repr(b'say "hi"'), repr(b"'\""))
d: dict[bytes, int] = {b"a": 1, b"b": 2}
d[b"c"] = 3
print(d, d[b"a"], b"b" in d, sorted(d))
s: set[bytes] = {b"x", b"y"}
print(b"x" in s, len(s))


def f(x: bytes) -> bytes:
    return x + b"!"


print(f(b"hi"))
o: bytes | None = None
print(o is None)
o = b"z"
if o is not None:
    print(o)
lst: list[bytes] = [b"a", b"b"]
print(lst, sorted([b"b", b"a", b"ab"]), max(lst), min(lst))
t = (b"k", 1)
print(t, t[0])
try:
    print(b[10])
except IndexError as ex:
    print("IndexError", ex)
print(b"ab" b"cd", rb"\x41", b"\101\x42C")
print(bytes(range(65, 70)), bytes(x + 1 for x in b), bytes(map(lambda v: v ^ 32, b)), bytes(reversed(b)))
import sys

print(sys.byteorder, b"\xff\xfe" if sys.byteorder == "little" else b"\xfe\xff")  # (codecs.BOM_UTF16)
