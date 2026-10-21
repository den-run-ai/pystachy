# codecs: lib/codecs.py, CPython 3.13's with its marked edits, on lib/_pystachy_codecs.py, the
# stand-in Pystachy loads for CPython's C module _codecs, against CPython's: the BOM constants,
# encode() and decode(), the UTF-8, Latin-1 and ASCII codec functions with every error handler
# (also UTF-8 decoding that is not final: the tail it leaves, a truncated surrogate, an invalid
# sequence before the tail), the charmap codec on cp1252's table and on a table whose first
# character is not U+0000, lookup_error() and register_error(), the incremental classes derived
# from with methods, and the C module's functions bound in a class body, which no object binds
import codecs

HANDLERS = ["strict", "replace", "ignore", "backslashreplace", "xmlcharrefreplace", "surrogateescape", "surrogatepass", "nope"]


def show(r: tuple[str, int]) -> None:
    print(repr(r[0]), r[1])


def showb(r: tuple[bytes, int]) -> None:
    print(r[0], r[1])


def enc(f: int, s: str, e: str) -> None:
    try:
        if f == 0:
            showb(codecs.utf_8_encode(s, e))
        elif f == 1:
            showb(codecs.latin_1_encode(s, e))
        else:
            showb(codecs.ascii_encode(s, e))
    except UnicodeEncodeError as x:
        print("UnicodeEncodeError:", x)
    except LookupError as x:
        print("LookupError:", x)
    except TypeError as x:
        print("TypeError:", x)


def dec(f: int, b: bytes, e: str, final: bool) -> None:
    try:
        if f == 0:
            show(codecs.utf_8_decode(b, e, final))
        elif f == 1:
            show(codecs.latin_1_decode(b, e))
        else:
            show(codecs.ascii_decode(b, e))
    except UnicodeDecodeError as x:
        print("UnicodeDecodeError:", x)
    except LookupError as x:
        print("LookupError:", x)
    except TypeError as x:
        print("TypeError:", x)


def cmap(b: bytes, e: str, table: str) -> None:
    try:
        show(codecs.charmap_decode(b, e, table))
    except UnicodeDecodeError as x:
        print("UnicodeDecodeError:", x)
    except TypeError as x:
        print("TypeError:", x)
    except LookupError as x:
        print("LookupError:", x)


def cmapenc(s: str, e: str, m: dict[int, int]) -> None:
    try:
        showb(codecs.charmap_encode(s, e, m))
    except UnicodeEncodeError as x:
        print("UnicodeEncodeError:", x)
    except LookupError as x:
        print("LookupError:", x)


print("constants")
print(codecs.BOM_UTF8, codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE, codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)
print(codecs.BOM, codecs.BOM_UTF16, codecs.BOM_UTF32, codecs.BOM32_LE, codecs.BOM64_BE)

print("encode and decode")
print(codecs.encode("é€"), codecs.encode("é", "latin-1"), codecs.encode("é", "ascii", "replace"), codecs.encode("x", "UTF8"))
print(codecs.decode(b"\xc3\xa9"), codecs.decode(b"\xe9", "latin-1"), codecs.decode(b"\xff", "ascii", "replace"))
try:
    codecs.encode(b"x", "latin-1")
except TypeError as x:
    print("TypeError:", x)
try:
    codecs.decode("x")
except TypeError as x:
    print("TypeError:", x)
try:
    codecs.encode("x", "nope")
except LookupError as x:
    print("LookupError:", x)

print("codecs")
for s in ["", "abc", "aé€😀", "\udcff", "a\ud800b", "\x80\xff"]:
    for e in HANDLERS:
        for f in range(3):
            enc(f, s, e)
for b in [b"", b"abc", b"a\xc3\xa9", b"\xff", b"a\xe2\x82", b"\xed\xa0", b"\xed\xa0\x80", b"S\xe1\xe0", b"\xf0\x9f\x98", b"\xe0\x80", b"\xc3"]:
    for e in HANDLERS:
        dec(0, b, e, True)
        dec(0, b, e, False)
        dec(1, b, e, True)
        dec(2, b, e, True)

print("charmap")
CP1252 = (
    "\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f"
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~\x7f"
    "€￾‚ƒ„…†‡ˆ‰Š‹Œ￾Ž￾"
    "￾‘’“”•–—˜™š›œ￾žŸ"
    "\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf"
    "\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf"
    "\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff"
)
OTHER = "ab￾" + "x" * 253  # (not U+0000 first: CPython's map is a dict of every character)
m1 = codecs.charmap_build(CP1252)
m2 = codecs.charmap_build(OTHER)
print(len(m2), sorted(m2.items()))  # (CPython's m1 is an EncodingMap, which has no items)
for b in [b"", b"caf\xe9 \x80", b"\x81", b"a\x8d\x9d", b"\xfe\xff"]:
    for e in HANDLERS:
        cmap(b, e, CP1252)
cmap(b"\x00\x02\x03", "strict", OTHER)
for s in ["café €", "aĀb", "Āā", "x\udc80\udcffy", "￾"]:
    for e in HANDLERS:
        cmapenc(s, e, m1)
cmapenc("￾", "strict", m2)
show(codecs.charmap_decode(b"\xe9"))
showb(codecs.charmap_encode("\xe9"))

print("error handlers")
print(codecs.lookup_error("strict") is codecs.strict_errors)
try:
    codecs.lookup_error("nope")
except LookupError as x:
    print("LookupError:", x)
try:
    codecs.strict_errors(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))
except UnicodeDecodeError as x:
    print("UnicodeDecodeError:", x)


def mine(exc: UnicodeError) -> tuple[str, int]:
    return ("?", 0)


codecs.register_error("mine", mine)
print(codecs.lookup_error("mine") is mine)


class IncrementalEncoder(codecs.IncrementalEncoder):
    def encode(self, input, final=False):
        return codecs.utf_8_encode(input, self.errors)[0]


class IncrementalDecoder(codecs.BufferedIncrementalDecoder):
    def _buffer_decode(self, input, errors, final):
        return codecs.utf_8_decode(input, errors, final)


class Codec(codecs.Codec):
    def encode(self, input, errors="strict"):
        return codecs.latin_1_encode(input, errors)

    def decode(self, input, errors="strict"):
        return codecs.latin_1_decode(input, errors)


class Functions:
    # (a builtin function in CPython, which no object binds)
    enc = codecs.utf_8_encode
    dec = codecs.utf_8_decode

    def run(self, s: str) -> str:
        return self.dec(self.enc(s)[0])[0]


print("incremental classes")
d = IncrementalDecoder()
print(repr(d.decode(b"a\xe2\x82")), repr(d.decode(b"\xac\xf0\x9f")), repr(d.decode(b"\x98\x80", True)), d.getstate())
d.decode(b"\xe2")
d.reset()
print(d.getstate())
try:
    d.decode(b"\xe2", True)
except UnicodeDecodeError as x:
    print("UnicodeDecodeError:", x)
ie = IncrementalEncoder("replace")
print(ie.encode("é€"), ie.errors)
co = Codec()
print(co.encode("é"), co.decode(b"\xe9"))
fs = Functions()
print(fs.run("aé€😀"), fs.enc("x"), Functions.dec(b"y"))
