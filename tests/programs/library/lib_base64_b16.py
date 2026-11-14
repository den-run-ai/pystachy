# base64's Base16 functions
import base64
import binascii

for d in [b"", b"f", b"foobar", b"\x00\xff\xfe\x10 hello", bytes(range(256))]:
    x = base64.b16encode(d)
    print(x, base64.b16decode(x) == d, base64.b16decode(x.decode()) == d, base64.b16decode(x.lower(), casefold=True) == d)
print(base64.b16decode(b"abcdef", casefold=True), base64.b16decode("ABCDEF"), base64.b16decode("aBcDeF", True))
for bad in [b"abcd", b"ABCDEFG", b"0G", b"01 23", b"0", b"\x8041"]:
    for fold in [False, True]:
        try:
            print(base64.b16decode(bad, fold))
        except binascii.Error as err:
            print("Error", bad, fold, err)
try:
    print(base64.b16decode("é"))
except ValueError as err:
    print("ValueError", err)
