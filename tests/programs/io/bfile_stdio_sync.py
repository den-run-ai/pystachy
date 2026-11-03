# A partial final buffer must not resurrect removed bytes after truncate or seek.
# Failed seeks retain the logical position, including when stdio has read ahead.
import os
import tempfile

p = os.path.join(tempfile.mkdtemp(), "data.bin")


def seed() -> None:
    with open(p, "wb") as f:
        f.write("".join(["row %d: abcdefghij\n" % i for i in range(12)]).encode())


def check(f) -> None:
    print("prime", f.truncate(231), f.readline())
    print("tail", f.seek(-14, 2), f.truncate(123), f.tell(), f.read(14), f.tell())
    print("start", f.seek(0), f.read(11), f.tell())
    at = f.tell()
    try:
        f.seek(-10000, 1)
    except OSError:
        print("failed seek", f.tell() == at, f.read(5))
    print("extend", f.seek(217), f.truncate(231), f.tell(), f.read(14))
    print("rewrite", f.seek(110), f.write(b"changed\n"), f.tell())
    print("readback", f.seek(110), f.readline(), f.tell())
    print("shrink", f.truncate(114), f.tell(), f.read(8))
    print("after shrink", f.seek(110), f.read())


seed()
with open(p, "r+b", buffering=64) as f:
    check(f)
seed()
with open(p, "r+b", buffering=2) as f:
    check(f)
seed()
with open(p, "r+b", buffering=7) as f:
    check(f)
seed()
with open(p, "r+b", buffering=4096) as f:
    check(f)
seed()
with open(p, "r+b", buffering=0) as f:
    check(f)
