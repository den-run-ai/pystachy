# the methods a bytearray shares with bytes: its own results are bytearrays


def show(*vs) -> None:
    print(*vs)


b = bytearray(b"  Hello, World! hello  ")
show(b.find(b"l"), b.find(b"l", 6), b.find(b"l", 6, 9), b.find(108), b.find(b"zz"), b.find(b""), b.find(b"", 100), b.find(bytearray(b"World")))
show(b.rfind(b"l"), b.rfind(b"l", 0, 10), b.rfind(108), b.rfind(b"zz"), b.index(b"H"), b.rindex(b"h"), b.count(b"l"), b.count(108), b.count(b"l", 5, 15), b.count(b""))
show(b.find(b"l", -8), b.find(b"l", -100, -10), b.find(b"o", 5, -3), b.index(b"o", -9))
for f in ["index", "rindex"]:
    try:
        if f == "index":
            b.index(b"zz")
        else:
            b.rindex(b"zz")
    except ValueError as e:
        show("ValueError:", e)
try:
    b.find(300)
except ValueError as e:
    show("ValueError:", e)
show(b.startswith(b"  He"), b.startswith(b"He", 2), b.startswith(b"He", 2, 3), b.startswith((b"x", b"  ")), b.startswith(bytearray(b" ")), b.startswith(b""), b.startswith(b"", 100))
show(b.endswith(b"lo  "), b.endswith(b"lo", 0, -2), b.endswith((b"x", b"y")), b.endswith(bytearray(b" ")), b.endswith(b"", 5, 2), b.startswith(b"llo", -7), b.endswith(b"hel", -100, -4))
show(b.strip(), b.lstrip(), b.rstrip(), b.strip(b" H"), b.strip(bytearray(b" o")), type(b.strip()).__name__)
show(b.split(), b.split(b","), b.split(b"l", 2), b.rsplit(b"l", 2), b.split(None, 1), b.rsplit(None, 1), bytearray(b"a\nb\r\nc").splitlines(), bytearray(b"a\nb\r\nc").splitlines(True))
show(b.partition(b","), b.rpartition(b"l"), b.partition(b"zz"), b.rpartition(bytearray(b"zz")))
show(b.replace(b"l", b"L"), b.replace(b"l", b"", 2), b.replace(bytearray(b"Hello"), bytearray(b"Bye")), b.replace(b"", b"-", 3))
show(b.upper(), b.lower(), b.swapcase(), bytearray(b"hello world").capitalize())
show(bytearray(b"ab").center(7), bytearray(b"ab").center(7, b"*"), bytearray(b"ab").ljust(5, b"."), bytearray(b"ab").rjust(5), bytearray(b"-42").zfill(6))
show(b.removeprefix(b"  "), b.removesuffix(b"  "), b.removeprefix(b"zz"), b.removesuffix(bytearray(b"o  ")))
show(bytearray(b"abc1").isalnum(), bytearray(b"abc").isalpha(), bytearray(b"\xff").isascii(), bytearray(b"123").isdigit(), bytearray(b"abc").islower(), bytearray(b" \t").isspace(), bytearray(b"AB").isupper(), bytearray().isalpha())
show(b.decode(), bytearray(b"h\xc3\xa9").decode("utf-8"), bytearray(b"h\xe9").decode("latin-1"), bytearray(b"h\xff").decode("ascii", "replace"), bytearray(b"\x00\xff\x10").hex(), bytearray().hex())
try:
    bytearray(b"h\xff").decode()
except UnicodeDecodeError as e:
    show("UnicodeDecodeError:", e)
nothing: list[bytes] = []
show(bytearray(b"-").join([b"a", b"b", b"c"]), bytearray(b", ").join([bytearray(b"x"), bytearray(b"y")]), bytearray().join([b"q"]), bytearray(b"-").join(nothing), b"/".join([bytes(bytearray(b"u")), b"v"]))
show(bytearray.fromhex("48 65 6c6C6f"), bytearray.fromhex(""), type(bytearray.fromhex("00")).__name__)
try:
    bytearray.fromhex("4x")
except ValueError as e:
    show("ValueError:", e)
table = bytearray.maketrans(b"abc", b"xyz")
show(bytearray(b"aabbcc d").translate(table), bytearray(b"aabbcc d").translate(table, b" a"), bytearray(b"hello").translate(None, b"l"), type(table).__name__)
r = b.upper()
r.append(33)
show(r, b)
parts = b.split()
parts[0].append(63)
show(parts, b)
