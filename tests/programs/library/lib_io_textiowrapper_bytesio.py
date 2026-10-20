# lib/io.py: io.TextIOWrapper over io.BytesIO, which is readable, writable and seekable, against
# CPython's. Every wrapper is closed before the program drops it: CPython's would close itself.
from io import BytesIO, TextIOWrapper

# reading a source file's lines as tokenize.open() does (line buffering), and closing the BytesIO
b = BytesIO("# coding: utf-8\nx = 'é€'\r\ny = 2\r\n".encode())
t = TextIOWrapper(b, "utf-8", line_buffering=True)
print(repr(t), t.encoding, t.line_buffering, t.buffer is b, t.seekable(), t.readable(), t.writable())
print(t.readlines(), b.tell(), t.closed)
t.close()
print(b.closed, t.closed)
try:
    b.getvalue()
except ValueError as e:
    print("ValueError:", e)

# the newline modes over the same bytes
for nl in [None, "", "\n", "\r", "\r\n"]:
    t = TextIOWrapper(BytesIO(b"a\nb\r\nc\rd"), encoding="ascii", newline=nl)
    print(repr(nl), [line for line in t])
    t.close()

# writing: the BytesIO holds the text once the wrapper flushes it, or writes 8192 bytes
b = BytesIO()
t = TextIOWrapper(b, encoding="utf-8", newline="\r\n")
print(t.write("héllo\nwörld\n"), b.getvalue())
t.flush()
print(b.getvalue(), b.tell())
print(t.write("x" * 9000), len(b.getvalue()), repr(t.read()))
t.close()
b = BytesIO()
t = TextIOWrapper(b, encoding="latin-1", write_through=True)
t.write("crème\n")
print(b.getvalue())
try:
    t.write("€")
except UnicodeEncodeError as e:
    print("UnicodeEncodeError:", e)
t.writelines(["a", "b"])
print(b.getvalue())
t.close()

# a read, a write and a read again: the write goes where the BytesIO is, after the chunk read
b = BytesIO(b"abc\ndef\n")
t = TextIOWrapper(b, encoding="ascii")
print(repr(t.readline()), b.tell(), t.write("X"), repr(t.read()))
t.flush()
print(b.getvalue(), repr(t.read()))
b.seek(0)
print(repr(t.read(5)), repr(t.readline()), b.tell())
t.close()

# email.parser's BytesParser: ASCII with surrogateescape, which carries the other bytes
b = BytesIO(b"Subject: caf\xe9\r\n\r\nbody \xff\r\n")
t = TextIOWrapper(b, encoding="ascii", errors="surrogateescape")
lines = t.readlines()
print([ascii(line) for line in lines], repr(t.newlines))
print([line.encode("ascii", "surrogateescape") for line in lines])
t.close()

# many lines, in the wrapper's chunks of 8192 bytes
text = "".join([f"line {i}: {'é' * (i % 7)}\n" for i in range(3000)])
b = BytesIO(text.encode())
t = TextIOWrapper(b, encoding="utf-8")
count = 0
same = True
for line in t:
    same = same and line == f"line {count}: {'é' * (count % 7)}\n"
    count += 1
print(count, same, t.read() == "", b.tell() == len(text.encode()))
t.close()
b = BytesIO(text.encode())
with TextIOWrapper(b, encoding="utf-8") as t:
    print(repr(t.read(10)), t.read(100000) == text[10:])  # (the first ten characters are ASCII)
print(b.closed)
