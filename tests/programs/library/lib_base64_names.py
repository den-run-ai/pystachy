# The ways a program names base64's functions, and the module's public names
import base64
import base64 as b64
from base64 import b32encode, b64encode as enc, urlsafe_b64decode

print(base64.__all__)
print(enc(b"hi"), b64.b64decode(b"aGk="), b32encode(b"hi"), urlsafe_b64decode("aGk="))
f = base64.b16encode
print(f(b"hi"), f(b""))


def twice(data: bytes) -> bytes:
    return base64.b64encode(base64.b64encode(data))


print(twice(b"hi"), base64.b64decode(base64.b64decode(twice(b"hi"))))
print([base64.b64encode(bytes([n])) for n in range(4)])
print({k: base64.b85encode(k.encode()) for k in ["a", "bc"]})
print(base64.b64encode(b"hi").decode("ascii") + "!", len(base64.b64encode(b"x" * 1000)))
