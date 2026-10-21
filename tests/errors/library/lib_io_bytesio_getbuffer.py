# error: 'io.BytesIO' object has no method 'getbuffer'
# lib/io's BytesIO has no getbuffer() (lib/README.md): CPython's returns a memoryview, a writable
# view of the buffer that the BytesIO cannot resize while it lives, and Pystachy has no memoryview
from io import BytesIO

b = BytesIO(b"1234567890")
view = b.getbuffer()
print(len(view))
