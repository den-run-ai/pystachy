# str.encode() and bytes.decode() with CPython's UTF-8, Latin-1 and ASCII codecs, their aliases
# and error handlers, and the errors they raise
def dec(b: bytes, enc: str, errors: str) -> None:
    try:
        print(repr(b.decode(enc, errors)))
    except UnicodeDecodeError as e:
        print("UnicodeDecodeError:", e)
    except LookupError as e:
        print("LookupError:", e)
    except TypeError as e:
        print("TypeError:", e)


def enc(s: str, encoding: str, errors: str) -> None:
    try:
        print(s.encode(encoding, errors))
    except UnicodeEncodeError as e:
        print("UnicodeEncodeError:", e)
    except LookupError as e:
        print("LookupError:", e)


for b in [b"plain", b"h\xc3\xa9llo \xe2\x82\xac \xf0\x9f\x98\x80", b"\xff", b"a\xc3", b"\xed\xa0\x80", b"\xe0\x80", b"\xf0\x90\x80", b"a\xf0\x90\x80b", b"\xc0\xaf", b"\xf4\x90\x80\x80"]:
    for errors in ["strict", "replace", "ignore", "backslashreplace", "surrogateescape"]:
        dec(b, "utf-8", errors)
dec(b"\xed\xa0\x80", "utf-8", "surrogatepass")
dec(b"\xed\xa0\x80x", "utf-8", "surrogatepass")
dec(b"\xffab", "ascii", "strict")
dec(b"\xffab", "ascii", "replace")
dec(b"\xffab\x80", "latin-1", "strict")
dec(b"x", "nope", "strict")
dec(b"\xff", "utf-8", "nope")
dec(b"\xff", "utf-8", "xmlcharrefreplace")
for name in ["UTF-8", "utf8", "U8", "Latin-1", "latin1", "ISO-8859-1", "iso_8859_1", "l1", "ASCII", "us-ascii", "646", " utf--8 "]:
    dec(b"ok\xc3\xa9", name, "replace")
for s in ["abc", "héllo", "€ uro", "ab€€c", "\U0001f600"]:
    for encoding in ["utf-8", "latin-1", "ascii"]:
        for errors in ["strict", "replace", "ignore", "backslashreplace", "xmlcharrefreplace"]:
            enc(s, encoding, errors)
esc = b"a\x80\xffb".decode("utf-8", "surrogateescape")
enc(esc, "utf-8", "surrogateescape")
enc(esc, "utf-8", "strict")
enc(esc, "latin-1", "surrogateescape")
enc(esc, "ascii", "strict")
sp = b"\xed\xa0\x80".decode("utf-8", "surrogatepass")
enc(sp, "utf-8", "surrogatepass")
enc(sp, "utf-8", "strict")
enc("x", "utf-8", "nope")
enc("€", "ascii", "nope")
enc("x", "nope", "strict")
print("é".encode() == b"\xc3\xa9", b"\xc3\xa9".decode() == "é", len("hé".encode("latin-1")))
