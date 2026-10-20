# bytes.maketrans(), translate() with a table, None and delete (by position and by name), and
# hex() with separators (str or bytes, by position and by name) in groups counted from either end,
# with the errors they raise as they run, also of arguments that may be None
t = bytes.maketrans(b"+/", b"-_")
print(len(t), t[43], t[47], t[0], t[255], b"".maketrans(b"aa", b"bc")[97])
print(b"a+b/c".translate(t), b"abc".translate(None), b"abcabc".translate(None, b"b"), b"abc".translate(t, delete=b"c"))
print(b"\x01\x02\x03".hex(":"), b"\x01\x02\x03".hex(":", 2), b"\x01\x02\x03".hex(b"-", -2), b"\x01\x02".hex(sep=" ", bytes_per_sep=0))
print(b"\x01\x02".hex(bytes_per_sep=2), b"".hex(":"), b"\x01\x02\x03\x04\x05".hex(" ", 9), b"\x01\x02".hex(":", True))
n: bytes | None = None
s: str | None = None
k: int | None = None


def case(i: int) -> None:
    try:
        if i == 0:
            print(bytes.maketrans(b"ab", b"c"))
        elif i == 1:
            print(b"x".translate(b"x"))
        elif i == 2:
            print(b"x".hex("::"))
        elif i == 3:
            print(b"x".hex("é"))
        elif i == 4:
            print(b"x".hex(b"\xff"))
        elif i == 5:
            print(b"x".hex(":", 2**31))
        elif i == 6:
            print(b"x".hex(":", -2**31 - 1))
        elif i == 7:
            print(b"x".translate(None, n))
        elif i == 8:
            print(bytes.maketrans(b"a", n))
        elif i == 9:
            print(b"x".hex(s))
        elif i == 10:
            print(b"x".hex(":", k))
        elif i == 11:
            print(b"x".hex(s, k))
        elif i == 12:
            print(b"\x01\x02".hex("€"), b"\x01\x02".hex("éé"))
    except (ValueError, OverflowError, TypeError) as e:
        print(type(e).__name__, e)


for i in range(13):
    case(i)
print(b"abc".translate(n), b"abc".translate(n, b"a"), b"\x01\x02".hex(b"\x00") == "01\x0002", b"\x01\x02\x03\x04".hex("é"[0:0] + ".", -3))
print(bytes(range(256)).translate(bytes.maketrans(bytes(range(256)), bytes(range(255, -1, -1))))[:4], b"\xff\x00".hex(":", -2147483648))
urlsafe = bytes.maketrans(b"+/", b"-_")
print(b"ab+/cd//".translate(urlsafe), b"ab-_cd".translate(bytes.maketrans(b"-_", b"+/")))
print(b"\x00\xff\x10".hex(), bytes(range(10)).hex(".", 4), bytes(range(10)).hex(".", -4), b"\xab".hex(":", 5))
