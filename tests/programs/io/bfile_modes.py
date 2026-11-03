# Binary files of each mode: the class CPython's open() makes (FileIO for buffering=0), its mode
# as FileIO names it, positions after reads and writes, appends, and exclusive creation
import os
import tempfile

d = tempfile.mkdtemp()
p = os.path.join(d, "m.bin")
with open(p, "wb") as f:
    f.write(b"0123456789")


def show(f) -> str:
    return type(f).__name__ + " " + f.mode + " " + repr(f).replace(d, "D")


with open(p, "r+b") as f:
    print(show(f))
    print(f.read(3), f.tell())
    print(f.write(b"ab"), f.tell())
    f.seek(0)
    print(f.read())
    print(f.seek(2), f.write(b"__"), f.read(2), f.tell())
print(open(p, "rb").read())

with open(p, "w+b") as f:
    print(show(f))
    f.write(b"hello")
    print(f.tell(), f.seek(1), f.read())

with open(p, "ab") as f:
    print(show(f), f.tell())
    f.write(b" world")
    print(f.tell())
with open(p, "a+b") as f:
    print(show(f), f.tell())
    print(f.seek(0), f.read(5))
    f.write(b"!")
print(open(p, "rb").read())

q = os.path.join(d, "new.bin")
with open(q, "xb") as f:
    print(show(f).replace("new.bin", "N"))
    f.write(b"x")
try:
    open(q, "xb")
except FileExistsError as e:
    print("FileExistsError", str(e).replace(d, "D"))
os.remove(q)
with open(q, "x+b") as f:
    print(show(f).replace("new.bin", "N"))

def raw(f) -> None:
    print(show(f))
    if f.readable():
        print(" ", f.read(2), f.tell())
    if f.writable():
        print(" ", f.write(b"Z"), f.tell())
    f.close()
    print(" ", repr(f), f.closed)


raw(open(p, "rb", buffering=0))
raw(open(p, "r+b", buffering=0))
raw(open(p, "wb", buffering=0))
raw(open(p, "ab", buffering=0))
raw(open(p, "a+b", buffering=0))
f = open(p, "rb", 0)
print(f.readall(), f.read(), f.read(3))
f.seek(0)
print(f.readline(), f.readlines())
f.close()
with open(p, "rb", buffering=4096) as f:
    print(show(f), f.read(4))
with open(p, "rb", buffering=-5) as f:
    print(show(f), f.read(4))
print(open(p, "br").read(), open(p, "rb").mode, open(p, mode="rb").read(2))
