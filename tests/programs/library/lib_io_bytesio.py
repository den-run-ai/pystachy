# lib/io.py: Pystachy's io.BytesIO, against CPython's (Modules/_io/bytesio.c). Cases after
# CPython's Lib/test/test_memoryio.py.
import io
import sys
from io import BytesIO

# construction: no argument, bytes, None, by keyword; __init__ called again
print(BytesIO().getvalue(), BytesIO(b"abc").getvalue(), BytesIO(None).getvalue(), BytesIO(initial_bytes=b"kw").getvalue())
b = BytesIO(b"1234567890")
print(b.read(3), b.tell())
b.__init__(b"xy")
print(b.tell(), b.getvalue(), b.read())
b.__init__()
print(b.tell(), b.getvalue(), b.closed)
# without bytes, a closed one stays closed; with bytes, it is open again
b.close()
b.__init__(None)
print(b.closed)
b.__init__(b"again")
print(b.closed, b.getvalue())

# reading: read(), read(n), read(0), read(-1), read(None), read1(); at and past the end
buf = b"1234567890"
b = BytesIO(buf)
print(b.read(0), b.read(1), b.read(4), b.read(900), b.read(), b.tell())
b.seek(0)
print(b.read(-1), b.seek(0), b.read(None), b.seek(2), b.read(-5), b.tell())
b.seek(len(buf) + 1)
print(b.read(1), b.read(), b.tell())
b.seek(100)
print(b.read(), b.tell(), b.getvalue())
print(BytesIO(buf).read1(), BytesIO(buf).read1(-1), BytesIO(buf).read1(3), BytesIO(buf).read1(None))
b = BytesIO(buf)
print(b.read1(4), b.read1(0), b.read1(100), b.read1(), b.tell())

# readline: \n alone ends a line (not \r); a size limits the bytes it returns
line = b"1234567890\n"
b = BytesIO(line * 2)
print(b.readline(0), b.readline(), b.readline(), b.readline(), b.tell())
b.seek(0)
print(b.readline(5), b.readline(5), b.readline(5), b.readline(-1), b.readline(None), b.readline())
b = BytesIO((line * 3)[:-1])
print(b.readline(), b.readline(), b.readline(), b.readline())
b = BytesIO(b"a\rb\r\nc\n\nd")
print([b.readline() for _ in range(6)])
b.seek(len(line) * 2 + 1)
print(b.readline(), b.tell())

# readlines: a size bounds the total, which stops the lines once it is reached (0, a negative size
# or None: no bound)
b = BytesIO(line * 10)
print(len(b.readlines()), b.readlines(), b.seek(5), b.readlines()[:2])
for size in [-1, 0, 1, 10, 11, 12, 15, 22, 23, None]:
    b.seek(0)
    print(size, len(b.readlines(size)), b.tell())
print(BytesIO(b"a\nb\nc\n").readlines(2), BytesIO(b"ab\ncd\n").readlines(3), BytesIO(b"x").readlines())
b.seek(len(line) * 10 + 1)
print(b.readlines(), b.tell())

# iteration: the object is its own iterator, reading a line at a time from the shared position
b = BytesIO(b"one\ntwo\nthree")
print(iter(b) is b, next(b))
for x in b:
    print(x)
print(list(b), list(BytesIO(b"")), list(BytesIO(b"\n\n")), [x for x in BytesIO(b"p\nq")])
b.seek(4)
print(list(b), b.tell())
try:
    next(BytesIO(b""))
except StopIteration:
    print("StopIteration")

# writing: at the end, over the bytes, past the end (NUL bytes fill the gap), nothing past it
b = BytesIO()
print(b.write(b"blah."), b.seek(0), b.write(b"Hello."), b.tell(), b.seek(5), b.write(b" world\n\n\n"), b.getvalue())
print(b.seek(0), b.write(b"h"), b.truncate(12), b.tell(), b.getvalue())
b = BytesIO(b"hello world\n")
b.seek(6)
print(b.write(b"WO"), b.tell(), b.getvalue(), b.write(b"RLD!!!!!!"), b.getvalue(), b.tell())
b = BytesIO(buf)
print(b.seek(len(buf) + 1), b.read(), b.tell(), b.getvalue())
print(b.write(b""), b.getvalue(), b.tell(), b.write(buf), b.getvalue(), b.tell())
b = BytesIO(b"abc")
print(b.seek(6), b.write(b"Z"), b.getvalue(), b.seek(1), b.write(b"Q"), b.getvalue())
parts = BytesIO()
for i in range(1000):
    parts.write(str(i).encode())
    parts.write(b",")
value = parts.getvalue()
print(len(value), value[:20], value[-10:], parts.tell())

# writelines: any iterable of bytes; nothing is added between them
empty: list[bytes] = []
b = BytesIO()
print(b.writelines([buf] * 3), b.getvalue(), b.tell())
b.writelines(empty)
b.writelines((b"-", b"+"))
b.writelines(s.encode() for s in ["x", "y"])
b.seek(0)
b.writelines([b"AB", b"C"])
print(b.getvalue(), b.tell())

# getvalue: whatever the position
b = BytesIO(buf)
print(b.getvalue(), b.read(), b.getvalue(), BytesIO(buf * 1000).getvalue()[-3:])

# seek and tell: whence 0, 1 and 2, and the errors
b = BytesIO(buf)
print(b.read(5), b.seek(0), b.seek(0, 0), b.seek(3), b.seek(0, 1), b.read(), b.seek(len(buf)), b.read(), b.seek(0, 2))
print(b.seek(0), b.seek(-1, 1), b.seek(3, 1), b.seek(-4, 1), b.seek(-1, 2), b.seek(1, 1), b.seek(1, 2), b.seek(-100, 2))
b.seek(-3, 2)
print(b.read(), b.seek(0), b.seek(1, 1), b.read(), b.seek(10000), b.tell(), b.read(4))
print(b.seek(sys.maxsize), b.read(4), b.seek(sys.maxsize - 2), b.read(4), b.tell(), b.seek(0, io.SEEK_SET), io.SEEK_SET, io.SEEK_CUR, io.SEEK_END)
for pos, whence in [(-1, 0), (1, -1), (1, 3), (-2, 3), (0, 2**31), (0, -2**31 - 1), (0, 2**31 - 1), (0, -2**31), (-sys.maxsize - 1, 0)]:
    try:
        b.seek(pos, whence)
    except ValueError as e:
        print("ValueError:", e)
    except OverflowError as e:
        print("OverflowError:", e)
b = BytesIO(b"abc")
b.seek(sys.maxsize)
for pos, whence in [(1, 1), (0, 1), (sys.maxsize - 2, 2), (sys.maxsize - 3, 2), (sys.maxsize, 2)]:
    try:
        print(b.seek(pos, whence))
    except OverflowError as e:
        print("OverflowError:", e)
b.seek(sys.maxsize)
try:
    b.write(b"x")
except OverflowError as e:
    print("OverflowError:", e)
print(b.write(b""), b.getvalue())

# truncate: to the position, or to a size; the position stays where it was
b = BytesIO(buf)
try:
    b.truncate(-1)
except ValueError as e:
    print("ValueError:", e)
b.seek(6)
print(b.truncate(8), b.getvalue(), b.truncate(), b.getvalue(), b.truncate(4), b.getvalue(), b.tell())
print(b.seek(0, 2), b.write(buf), b.getvalue(), b.truncate(None), b.tell(), b.truncate(100), b.getvalue())
b.seek(50)
print(b.truncate(), b.getvalue(), b.tell(), b.write(b"!"), len(b.getvalue()), b.truncate(0), b.getvalue(), b.tell())

# the flags, closing, and every operation on a closed BytesIO; closed cannot be assigned
b = BytesIO()
print(b.writable(), b.readable(), b.seekable(), b.isatty(), b.flush(), b.closed)
try:
    b.closed = True
except AttributeError as e:
    print("AttributeError:", e)
print(b.close(), b.close(), b.closed)
it = iter(b)
print(it is b)
for name in ["getvalue", "read", "read1", "readline", "readlines", "write", "write empty", "writelines", "tell", "seek",
             "truncate", "readable", "writable", "seekable", "isatty", "flush", "next", "for", "with"]:
    try:
        if name == "getvalue":
            b.getvalue()
        elif name == "read":
            b.read()
        elif name == "read1":
            b.read1(1)
        elif name == "readline":
            b.readline()
        elif name == "readlines":
            b.readlines()
        elif name == "write":
            b.write(b"y")
        elif name == "write empty":
            b.write(b"")
        elif name == "writelines":
            b.writelines(empty)
        elif name == "tell":
            b.tell()
        elif name == "seek":
            b.seek(0)
        elif name == "truncate":
            b.truncate(0)
        elif name == "readable":
            b.readable()
        elif name == "writable":
            b.writable()
        elif name == "seekable":
            b.seekable()
        elif name == "isatty":
            b.isatty()
        elif name == "flush":
            b.flush()
        elif name == "next":
            next(b)
        elif name == "for":
            for x in b:
                print(x)
        else:
            with b:
                print("entered")
    except ValueError as e:
        print(name, "ValueError:", e)
# whence is checked before the stream is
try:
    b.seek(0, 2**31)
except OverflowError as e:
    print("OverflowError:", e)

# with: the block's value is the object, which is closed as the block is left, also by an exception
with BytesIO(b"data\nmore") as f:
    print(f.readline(), f.closed)
print(f.closed)
try:
    with BytesIO() as g:
        g.write(b"x")
        raise KeyError("k")
except KeyError as e:
    print("KeyError:", e, g.closed)

# bound methods as values, as encodings.uu_codec takes them
infile = BytesIO(b"abcdefgh")
outfile = BytesIO()
read = infile.read
write = outfile.write
chunk = read(3)
while chunk:
    write(chunk.upper())
    chunk = read(3)
print(outfile.getvalue(), infile.tell(), outfile.tell())


# a function of a BytesIO, and one class holding one
def lines_of(f: BytesIO) -> list[bytes]:
    return [x.rstrip(b"\n") for x in f]


class Holder:
    def __init__(self) -> None:
        self.fp = BytesIO()

    def put(self, s: str) -> None:
        self.fp.write(s.encode("ascii"))


h = Holder()
h.put("a\nb\n")
h.put("c")
h.fp.seek(0)
print(lines_of(h.fp), h.fp.getvalue())
