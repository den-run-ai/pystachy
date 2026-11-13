# base64's Base32 functions: both alphabets, casefold, map01, padding and digit errors
import base64
import binascii

data = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar", b"\x00\xff\xfe\x10 hello", bytes(range(256))]
for d in data:
    e = base64.b32encode(d)
    print(e, base64.b32decode(e) == d, base64.b32decode(e.decode()) == d)
    h = base64.b32hexencode(d)
    print(h, base64.b32hexdecode(h) == d, base64.b32hexdecode(h.decode()) == d)

print("-- casefold and map01")
print(base64.b32decode(b"mzxw6===", casefold=True), base64.b32decode("mZxW6ytB", True), base64.b32hexdecode(b"cpnmu===", True))
print(base64.b32decode(b"M1023456", map01=b"L"), base64.b32decode(b"M1023456", map01="I"), base64.b32decode(b"m1o23456", True, b"l"))
for m in [b"LL", b""]:
    try:
        print(base64.b32decode(b"MZXW6===", map01=m))
    except AssertionError as err:
        print("AssertionError", err)
try:
    print(base64.b32decode(b"MZXW6===", map01="IL"))
except AssertionError as err:
    print("AssertionError", err)

print("-- errors")
for bad in [b"MZXW6", b"MZXW6==", b"MZXW6=======", b"mzxw6===", b"M1======", b"MZ=W6===", b"MZXW6Y==", b"========",
            b"M=======", b"MZX=====", b"MZXW6Y=A", b"MZXW6YT!"]:
    try:
        print(base64.b32decode(bad))
    except binascii.Error as err:
        print("Error", bad, err)
    try:
        print(base64.b32hexdecode(bad))
    except binascii.Error as err:
        print("Error hex", bad, err)
try:
    print(base64.b32decode("MZXW6é=="))
except ValueError as err:
    print("ValueError", err)
