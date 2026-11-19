# librt.base64 (lib/librt/base64.py here, librt 0.16.0's C extension in CPython): the four
# functions' results, the characters the decoders ignore, and the extension's errors, which are
# not base64's.
import librt.base64
from librt.base64 import b64decode, b64encode, urlsafe_b64decode, urlsafe_b64encode

data = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar", b"\x00\xff\xfe\x10 hello", b"\xfb\xff\xbe", bytes(range(256))]
for d in data:
    e = b64encode(d)
    u = urlsafe_b64encode(d)
    print(e, u)
    print(b64decode(e) == d, b64decode(e.decode("ascii")) == d, urlsafe_b64decode(u) == d, urlsafe_b64decode(u.decode()) == d,
          urlsafe_b64decode(e) == d, librt.base64.b64encode(d) == e)

print("-- ignored characters")
for s in [b"aGVs\nbG8=\n", b"aGVs!bG8=", b" aGVs bG8= ", b"aGVsbG8=\x00\xff", b"aGVsbG8=====", b"aGk=aGk=", b"aG=k", b"a=Gk",
          b"=aGk", b"aGk", b"aGk\n", b"-_-_", b"+/+/", b"\n", b"=", b"====", b"aGVsbG8=aGVsbG8="]:
    for f in [0, 1]:
        try:
            print(s, f, b64decode(s) if f == 0 else urlsafe_b64decode(s))
        except ValueError as err:
            print(s, f, "ValueError", err)
        except RuntimeError as err:
            print(s, f, "RuntimeError", err)

print("-- errors")
for s in [b"a", b"aGVsbG8", b"aGVsbG8=", b"aG", b"aG=", b"aG==", b"a===", b"aGVsb===", b"a=", b"a==", b"a====", b"aGVsbA===="]:
    try:
        print(s, b64decode(s))
    except ValueError as err:
        print(s, "ValueError", type(err).__name__, err)
    except RuntimeError as err:
        print(s, "RuntimeError", err)
    try:
        print(s, urlsafe_b64decode(s.decode()))
    except ValueError as err:
        print(s, "ValueError", type(err).__name__, err)
    except RuntimeError as err:
        print(s, "RuntimeError", err)
for text in ["héllo", "€", "aGk=\x80"]:
    try:
        print(b64decode(text))
    except ValueError as err:
        print("ValueError", err)
    try:
        print(urlsafe_b64decode(text))
    except ValueError as err:
        print("ValueError", err)
print(b64decode("aGk="), urlsafe_b64decode("-_8="), b64decode(""), urlsafe_b64decode(b""))

print("-- an argument that is neither bytes nor str")
try:
    print(b64decode(5))
except TypeError as err:
    print("TypeError", err)
try:
    print(urlsafe_b64decode(None))
except TypeError as err:
    print("TypeError", err)
