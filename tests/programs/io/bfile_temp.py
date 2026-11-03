# A binary file used in one expression is closed right after that use, as CPython's finalizer
# closes it, so its writes are in the file when the next statement looks (a file dropped
# otherwise is closed at a collection: docs/language/compatibility.md#memory-and-resource-lifetime)
import os
import tempfile

d = tempfile.mkdtemp()
p = os.path.join(d, "t.bin")
print(open(p, "wb").write(b"abc"), os.path.getsize(p))
print(open(p, "ab").write(b"de"), os.path.getsize(p))
print(open(p, "rb").read(), len(open(p, "rb").read(2)))
print(open(p, "r+b").write(b"A"), os.path.getsize(p), open(p, "rb").read())
print(open(p, "ab", buffering=0).write(b"!"), os.path.getsize(p))
for i in range(3):
    open(p, "ab").write(bytes([65 + i]))
print(open(p, "rb").read())
with open(p, "rb") as f:
    print(f.read(1))
