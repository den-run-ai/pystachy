# base64's Ascii85 functions: folding, padding, Adobe framing, wrapping and errors
import base64

data = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar", b"\x00\x00\x00\x00", b"    ", b"\x00\x00\x00\x00\x00",
        b"\xff\xff\xff\xff", bytes(range(256)), b"\x00" * 3, b"a" * 9 + b"    " + b"\x00" * 8]
for d in data:
    a = base64.a85encode(d)
    print(a, base64.a85decode(a) == d, base64.a85decode(a.decode()) == d)
    f = base64.a85encode(d, foldspaces=True)
    print(f, base64.a85decode(f, foldspaces=True) == d)
    ad = base64.a85encode(d, adobe=True)
    print(ad, base64.a85decode(ad, adobe=True) == d)
    p = base64.a85encode(d, pad=True)
    print(p, len(p) % 5, base64.a85decode(p)[:len(d)] == d)

print("-- wrapcol")
long = bytes(range(60))
for w in [1, 2, 7, 20, 100]:
    print(base64.a85encode(long, wrapcol=w)[:60])
    print(base64.a85encode(long, wrapcol=w, adobe=True)[-30:])
print(base64.a85encode(b"abc", wrapcol=3, adobe=True), base64.a85encode(b"", wrapcol=1, adobe=True))
print(base64.a85encode(b"abcdefgh", foldspaces=False, wrapcol=5, pad=True, adobe=True))

print("-- decoding")
print(base64.a85decode(b" 87cUR \n D]i,\t\"Ebo80 "), base64.a85decode(b"<~87cURD]i,\"Ebo80~>", adobe=True),
      base64.a85decode(b"87cURD]i,\"Ebo80~>", adobe=True))
print(base64.a85decode(b"87cURxD]i", ignorechars=b"x"), base64.a85decode("87cUR D]i", foldspaces=False, adobe=False, ignorechars=b" "))
for bad, how in [(b"s8W-\"", 0), (b"87cURD]i,\"Ebo80", 1), (b"abzcd", 0), (b"abycd", 2), (b"ab\x80", 0), (b"87 cU", 3),
                 (b"vwxyz", 0), (b"y", 0), (b"<~~", 1)]:
    try:
        if how == 0:
            print(base64.a85decode(bad))
        elif how == 1:
            print(base64.a85decode(bad, adobe=True))
        elif how == 2:
            print(base64.a85decode(bad, foldspaces=True))
        else:
            print(base64.a85decode(bad, ignorechars=b""))
    except ValueError as err:
        print("ValueError", bad, err)
