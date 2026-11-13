# base64's Base64 functions: the standard and URL-safe alphabets, altchars, validation, errors
import base64
import binascii

data = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar", b"\x00\xff\xfe\x10 hello", bytes(range(256))]
for d in data:
    e = base64.b64encode(d)
    print(e, base64.b64decode(e) == d, base64.b64decode(e.decode("ascii")) == d)
    print(base64.standard_b64encode(d) == e, base64.standard_b64decode(e) == d, base64.standard_b64decode(e.decode()) == d)
    u = base64.urlsafe_b64encode(d)
    print(u, base64.urlsafe_b64decode(u) == d, base64.urlsafe_b64decode(u.decode()) == d)

print("-- altchars")
print(base64.b64encode(b"\xfb\xff\xbe", altchars=b"-_"), base64.b64encode(b"\xfb\xff\xbe", b"*$"))
print(base64.b64decode(b"-_--", altchars=b"-_"), base64.b64decode("*$**", altchars="*$"), base64.b64decode(b"-_--", b"-_", True))
for alt in [b"abc", b"a", b""]:
    try:
        print(base64.b64encode(b"x", altchars=alt))
    except AssertionError as err:
        print("AssertionError", err)
    try:
        print(base64.b64decode(b"aaaa", altchars=alt))
    except AssertionError as err:
        print("AssertionError", err)

print("-- characters outside the alphabet")
print(base64.b64decode(b"aGVs\nbG8=\n"), base64.b64decode(b"aGVs!bG8="), base64.b64decode(b"aGVs bG8="))
print(base64.urlsafe_b64decode(b"-_+/"), base64.urlsafe_b64decode("-_+/"))
for bad in [b"aGVsbG8", b"a", b"aGVs!bG8=", b"aGVsbG8=\n", b"=aGVsbG8", b"aGVsbG8==", b"aGVsbG8=aGVsbG8=", b"aGk=aGk="]:
    for strict in [False, True]:
        try:
            print(base64.b64decode(bad, validate=strict))
        except binascii.Error as err:
            print("Error", bad, strict, err)
for text in ["héllo", "€", "a\x80"]:
    try:
        print(base64.b64decode(text))
    except ValueError as err:
        print("ValueError", err)
    try:
        print(base64.urlsafe_b64decode(text))
    except ValueError as err:
        print("ValueError", err)
print(issubclass(binascii.Error, ValueError))
