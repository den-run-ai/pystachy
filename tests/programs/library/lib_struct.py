# struct (lib/struct.py, CPython's, on lib/_pystachy_struct.py, the stand-in Pystachy loads for the
# C module _struct): pack(), unpack(), unpack_from(), iter_unpack() and calcsize() of formats the
# program gives as literals, module constants and Struct objects: every code in the native and
# standard tables and both byte orders, native alignment and pad bytes, the bytes codes cut and
# padded, floats at the edges of their formats, and struct.error and OverflowError with CPython's
# messages, as the program runs
import struct
from struct import Struct, calcsize, pack, unpack

HEADER = "<4sHHI"  # (a module's constant, as zipfile's)


def show(name: str, b: bytes) -> None:
    print(name, b.hex(" "))


show("ints <", pack("<bBhHiIlLqQ", -1, 255, -2, 65535, -3, 4294967295, -4, 4294967295, -5, 9223372036854775807))
show("ints >", pack(">bBhHiIlLqQ", -128, 0, -32768, 1, -2147483648, 2, -2147483648, 3, -9223372036854775808, 4))
show("ints native", pack("@bhilqnNP", 1, 2, 3, 4, 5, -6, 7, 8))
show("ints =", pack("=hiq", 1, 2, 3))
# (ten values: a tuple of more than nine items is not printed, compared or hashed, see compatibility.md)
v0, v1, v2, v3, v4, v5, v6, v7, v8, v9 = unpack("<bBhHiIlLqQ", pack("<bBhHiIlLqQ", -1, 255, -2, 65535, -3, 4294967295, -4, 4294967295, -5, 9223372036854775807))
print(v0, v1, v2, v3, v4, v5, v6, v7, v8, v9)
print(unpack("@bhilqnNP", pack("@bhilqnNP", 1, 2, 3, 4, 5, -6, 7, 8)))
print(unpack(">i", b"\xff\xff\xff\xfe"), unpack("<q", b"\xff" * 8), unpack("@P", pack("@P", -1)[:7] + b"\x00"))
print(calcsize("@bi"), calcsize("@bq"), calcsize("@ib"), calcsize("@b0q"), calcsize("<bi"), calcsize("=bq"), calcsize(""), calcsize("3x2s5p"))
show("aligned", pack("@bihq", 1, 2, 3, 4))
show("pads", pack("<x2xb3x", 7))
print(unpack("<x2xb3x", b"\x00\x00\x00\x07\x00\x00\x00"))
show("bytes", pack("<c3s5p0s0p2sp", b"x", b"abcdef", b"ab", b"", b"zz", b"y", b"long"))
print(unpack("<c3s5p0s0p2sp", pack("<c3s5p0s0p2sp", b"x", b"abcdef", b"ab", b"", b"zz", b"y", b"long")))
print(unpack("<5p", b"\x09abcd"), unpack("<3s", b"a\x00b"), pack("<300p", b"q" * 400)[:3])
show("bools", pack("<???", 5, "", [1]))
print(unpack("<???", b"\x00\x01\x02"))


def flags(x: int | None, s: str | None) -> bytes:
    return pack("<??", x, s)  # (? packs any value's truth, also one that may be None)


print(flags(None, None).hex(), flags(3, "").hex(), flags(0, "a").hex())
for x in [0.0, -0.0, 1.5, -2.25, 1e-310, 3.4028234663852886e38, 65504.0, 65519.0, 2.0 ** -24, 2.0 ** -25, 3 * 2.0 ** -25, 1 / 3, 0.1]:
    he = pack("<e", x) if abs(x) < 65520.0 else b""
    hf = pack("<f", x)
    print(repr(x), he.hex(), hf.hex(), pack(">d", x).hex(), str(unpack("<e", he)[0]) if len(he) == 2 else "-", unpack("<f", hf)[0], unpack(">d", pack(">d", x))[0])
inf = float("inf")
nan = float("nan")
print(pack("<efd", inf, -inf, nan).hex(), unpack("<efd", pack("<efd", inf, -inf, nan)), pack("<d", 3).hex(), pack("<f", True).hex())
print(unpack("<f", b"\x00\x00\xc0\x7f"), unpack("<e", b"\x00\x7c"), unpack(">e", b"\xfc\x00"), unpack("<d", pack("<d", -0.0)))
h = pack(HEADER, b"PK\x03\x04", 20, 8, 123456)
print(h.hex(), unpack(HEADER, h), calcsize(HEADER))
s = Struct("!IH")
print(s.size, s.format, s.pack(258, 3).hex(), s.unpack(b"\x00\x00\x01\x02\x00\x03"), s.unpack_from(b"xx\x00\x00\x00\x09\x00\x01", 2))
print(list(s.iter_unpack(b"\x00\x00\x00\x01\x00\x02\x00\x00\x00\x03\x00\x04")))
packI = Struct("!I").pack
print(packI(7).hex(), [packI(i).hex() for i in range(3)])
args = (1, 2.5, b"z")
print(pack("<id1s", *args).hex(), pack(b"<h", 5).hex(), unpack(b">h", b"\x00\x05"))
print(unpack_from_all := struct.unpack_from("<H", b"abcd"), struct.unpack_from("<H", b"abcd", 2), struct.unpack_from("<H", b"abcdef", offset=-4))
print(list(struct.iter_unpack("<BB", b"abcd")), list(struct.iter_unpack("<H", b"")))


def fail(k: int) -> None:
    try:
        if k == 0:
            pack("<h", 40000)
        elif k == 1:
            pack("<B", -1)
        elif k == 2:
            pack("<Q", -1)
        elif k == 3:
            pack("@i", 2 ** 31)
        elif k == 4:
            pack("<c", b"ab")
        elif k == 5:
            unpack("<I", b"abc")
        elif k == 6:
            struct.unpack_from("<I", b"abcdef", 4)
        elif k == 7:
            struct.unpack_from("<H", b"abcd", -5)
        elif k == 8:
            struct.unpack_from("<I", b"abcdef", -2)
        elif k == 9:
            struct.iter_unpack("<H", b"abc")
        elif k == 10:
            struct.iter_unpack("<0H", b"abc")
        elif k == 11:
            pack("<f", 1e300)
        elif k == 12:
            pack("<e", 65520.0)
        elif k == 13:
            unpack("<I", bytes(5))
        elif k == 14:
            calcsize("<z" if k > 100 else "<" + "h" * k + "y")
        elif k == 15:
            calcsize("<2")
        elif k == 16:
            calcsize("99999999999999999999h")
        elif k == 17:
            Struct("<l").pack(2 ** 31)
    except struct.error as e:
        print("struct.error:", e)
    except OverflowError as e:
        print("OverflowError:", e)


for k in range(18):
    fail(k)
