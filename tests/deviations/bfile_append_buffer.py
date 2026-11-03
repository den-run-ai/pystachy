# Documented deviation: in a file opened "a+b", a write is at the file's end at once, as the OS
# appends it, so tell() and reads before the next flush show the file as it will be
# (lib/compatibility.md#binary-files). CPython's BufferedRandom keeps such a write in its buffer
# at the position it was made: until the buffer is flushed, tell() counts from there (6 here) and
# a read of the buffer shows the write in that place (b'hello!world'); the flush then appends it
import os
import tempfile

d = tempfile.mkdtemp()
p = os.path.join(d, "a.bin")
with open(p, "wb") as f:
    f.write(b"hello world")
with open(p, "a+b") as f:
    f.seek(0)
    f.read(5)
    f.write(b"!")
    print(f.tell())
    f.seek(0)
    print(f.read())
print(open(p, "rb").read())
