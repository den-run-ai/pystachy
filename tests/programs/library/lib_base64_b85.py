# base64's base85 and Z85 functions
import base64

data = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar", b"\x00\x00\x00\x00", b"    ", b"\xff\xff\xff\xff",
        bytes(range(256)), b"\x00" * 3]
for d in data:
    b = base64.b85encode(d)
    print(b, base64.b85decode(b) == d, base64.b85decode(b.decode()) == d)
    bp = base64.b85encode(d, pad=True)
    print(bp, len(bp) % 5, base64.b85decode(bp)[:len(d)] == d, base64.b85encode(d, True) == bp)
    z = base64.z85encode(d)
    print(z, base64.z85decode(z) == d, base64.z85decode(z.decode()) == d)
# the test vector of the Z85 specification (ZeroMQ RFC 32)
print(base64.z85encode(b"\x86\x4f\xd2\x6f\xb5\x59\xf7\x5b"), base64.z85decode(b"HelloWorld"))

print("-- errors")
for bad in [b"|NsC0~", b"abc d", b"\x80abcd", b"|NsC1", b"ab\ncd", b"~~~~~", b"0000\""]:
    try:
        print(base64.b85decode(bad))
    except ValueError as err:
        print("ValueError", bad, err)
    try:
        print(base64.z85decode(bad))
    except ValueError as err:
        print("ValueError z", bad, err)
for bad in [b"%nSc1", b"ab;cd", b"#####", b"abcd_", b"0000`"]:
    try:
        print(base64.z85decode(bad))
    except ValueError as err:
        print("ValueError z", bad, err)
try:
    print(base64.b85decode("é"))
except ValueError as err:
    print("ValueError", err)
