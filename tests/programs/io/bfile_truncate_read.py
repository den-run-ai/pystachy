# truncate() of a buffered binary file drops what it read ahead, as CPython's BufferedRandom rewinds
# its raw file to its position: reads after it see the file as it now is, from the position, which
# stays. A write between a read and the truncate() reaches the file first
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/f"
with open(p, "wb") as f:
    f.write(b"abcdefgh" * 2048)
with open(p, "r+b", buffering=4096) as f:
    print(f.read(1))
    print(f.truncate(1))
    print(f.tell())
    print(len(f.read()))
with open(p, "wb") as f:
    f.write(b"abcdefgh" * 2048)
with open(p, "r+b", buffering=4096) as f:
    print(f.read(2))
    print(f.write(b"Q"))
    print(f.truncate(5))
    print(f.tell())
    print(f.read())
    print(f.write(b"Z"))
    f.seek(0)
    print(f.read())
with open(p, "r+b") as f:
    print(f.read(3))
    print(f.truncate())
    print(f.read())
    print(f.seek(0, 2))
with open(p, "r+b", buffering=0) as f:
    print(f.read(1))
    print(f.truncate(2))
    print(f.read())
os.remove(p)
os.rmdir(d)
