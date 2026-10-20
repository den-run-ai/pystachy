# lib/io.py: Pystachy's io.StringIO, against CPython's (Modules/_io/stringio.c). Cases after
# CPython's Lib/test/test_memoryio.py.
import io
from io import StringIO

# reading: read(), read(n), readline(), readline(n), readlines(), readlines(hint), iteration
s = StringIO("ab\ncd\r\nef\rgh")
print(repr(s.readline()), repr(s.readline()), repr(s.readline()), s.tell(), repr(s.readline()))
s = StringIO("hello\nworld\n")
print(repr(s.read(3)), repr(s.read(0)), s.tell(), repr(s.read(-5)), repr(s.read()), s.tell())
s.seek(0)
print(repr(s.readline(2)), repr(s.readline(0)), repr(s.readline(-1)), repr(s.readline(100)), repr(s.readline()))
s.seek(0)
print(s.readlines(), s.readlines(), s.seek(0), s.readlines(3), s.readlines(None))
# hint is a threshold: the lines stop once their total is past it, not at it
for h in [1, 2, 3, 4, 5, 6]:
    print(h, StringIO("a\nb\nc\n").readlines(h), StringIO("ab\ncd\n").readlines(h))
s.seek(1)
print(repr(s.read(None)), s.seek(0), repr(s.readline(None)))
s.seek(0)
for line in s:
    print(repr(line))
print([line for line in StringIO("x\ny")], list(StringIO("")), list(StringIO("one")))

# the newline modes: None translates \r\n and \r as they are written, "" ends lines at each,
# "\r" and "\r\n" write each \n as themselves and end lines there
for nl in [None, "", "\n", "\r", "\r\n"]:
    t = StringIO("ab\ncd\r\nef\rgh", newline=nl)
    print(repr(nl), repr(t.getvalue()), [t.readline() for _ in range(4)])
    t = StringIO(newline=nl)
    print(t.write("a\r"), t.write("\nb\n"), repr(t.getvalue()), t.tell())
t = StringIO("a\rb\r\nc", newline="")
print([t.readline(1), t.readline(2), t.readline(2), t.readline()])
t = StringIO("x\r", newline="")
print(repr(t.readline()), repr(t.readline()))

# writing: at the end, over the text, past its end (NULs fill the gap), writelines, truncate
s = StringIO()
print(s.write("abc"), s.seek(1), s.write("Z"), repr(s.getvalue()), s.tell())
print(s.writelines(["1", "2", "3"]), repr(s.getvalue()), s.tell())
s.seek(0)
print(s.write("xyzzy-long"), repr(s.getvalue()), s.tell())
s = StringIO("hello")
print(s.seek(8), s.write("X"), repr(s.getvalue()), s.tell(), s.seek(20), s.write(""), repr(s.getvalue()), s.tell())
s = StringIO("hello world")
s.seek(6)
print(s.truncate(), repr(s.getvalue()), s.tell(), s.truncate(2), repr(s.getvalue()), s.tell(), s.truncate(50), repr(s.getvalue()))
print(repr(s.read()), s.write("!"), repr(s.getvalue()))
parts = StringIO()
for i in range(1000):
    parts.write(str(i))
    parts.write(",")
value = parts.getvalue()
print(len(value), value[:20], value[-10:], parts.tell())
print(StringIO(None).getvalue() == "", StringIO("").getvalue() == "", StringIO("x").tell())

# seek and tell, and their errors
s = StringIO("hello")
print(s.seek(3), s.tell(), s.seek(0, 1), s.seek(0, 2), s.seek(0, io.SEEK_SET), io.SEEK_SET, io.SEEK_CUR, io.SEEK_END)
for pos, whence in [(-1, 0), (1, 1), (-2, 1), (1, 2), (0, 3), (5, -1)]:
    try:
        s.seek(pos, whence)
    except ValueError as e:
        print("ValueError:", e)
    except OSError as e:
        print("OSError:", e)
try:
    s.truncate(-1)
except ValueError as e:
    print("ValueError:", e)
try:
    StringIO(newline="x")
except ValueError as e:
    print("ValueError:", e)

# a closed StringIO: every operation raises, close() again does nothing
s = StringIO("x")
print(s.closed, s.readable(), s.writable(), s.seekable(), s.isatty(), s.line_buffering, s.encoding, s.errors)
s.close()
s.close()
s.flush()
print(s.closed)
for name in ["getvalue", "read", "readline", "readlines", "write", "writelines", "tell", "seek", "truncate", "readable", "isatty", "iter"]:
    try:
        if name == "getvalue":
            s.getvalue()
        elif name == "read":
            s.read()
        elif name == "readline":
            s.readline()
        elif name == "readlines":
            s.readlines()
        elif name == "write":
            s.write("y")
        elif name == "writelines":
            s.writelines(["y"])
        elif name == "tell":
            s.tell()
        elif name == "seek":
            s.seek(0)
        elif name == "truncate":
            s.truncate()
        elif name == "readable":
            s.readable()
        elif name == "isatty":
            s.isatty()
        else:
            for line in s:
                print(line)
    except ValueError as e:
        print(name, "ValueError:", e)

# print(file=...) writes into a StringIO, piece by piece
out = StringIO()
print("total", 3, 4.5, sep=", ", file=out)
print("done", end="", file=out)
print(repr(out.getvalue()), out.tell())
out.seek(0)
print(out.readlines())
