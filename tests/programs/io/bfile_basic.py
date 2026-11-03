# Binary files: open() of a mode with "b" reads and writes bytes as they are, as CPython's
# BufferedReader and BufferedWriter do
import os
import tempfile

d = tempfile.mkdtemp()
p = os.path.join(d, "data.bin")
data = bytes(range(256)) + b"\r\n\r\nend"
with open(p, "wb") as f:
    print(type(f).__name__, f.mode, f.closed, f.name == p)
    print(repr(f) == "<_io.BufferedWriter name=" + repr(p) + ">")
    print(f.write(data), f.tell())
    print(f.writable(), f.readable(), f.seekable(), f.isatty())
print(f.closed, os.path.getsize(p))

with open(p, "rb") as f:
    print(type(f).__name__, f.mode, repr(f) == "<_io.BufferedReader name=" + repr(p) + ">")
    print(f.read(3), f.tell())
    print(f.read() == data[3:])
    print(f.read(), f.read(5), f.tell())
    print(f.seek(10), f.read(2), f.seek(-4, 2), f.read(), f.seek(-6, 1), f.read(2))
    print(f.seek(0), f.read(0), f.read(None)[:4])
    print(f.readable(), f.writable(), f.seekable())

with open(p, "rb") as f:
    lines = f.readlines()
    print(len(lines), lines[0][-3:], lines[-1])
    f.seek(0)
    print(f.readline(4), f.readline(None)[:2], f.readline(-1)[:3])
    f.seek(0)
    print(f.readlines(20) == lines[:1])
    f.seek(0)
    n = 0
    for line in f:
        n += len(line)
    print(n)
    print(f.readline(), f.readline(3))

with open(p, "rb") as f:
    print(f.read() == data)
print(open(p, "rb").read()[250:])
