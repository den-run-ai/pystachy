# error: 'io.BytesIO' object has no method 'readinto'
# lib/io's BytesIO has no readinto() (lib/README.md): CPython's reads into a writable buffer, a
# bytearray, memoryview or array, and Pystachy has none of them (CPython raises TypeError for a
# bytes, which cannot be written)
from io import BytesIO

b = BytesIO(b"1234567890")
print(b.readinto(b"hello"))
