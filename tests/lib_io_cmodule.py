# _io, which CPython builds into its interpreter, under io: the classes and functions it has here
import _io
import io
import tempfile

print(_io.__doc__.splitlines()[0], len(_io.__doc__))
print(_io.DEFAULT_BUFFER_SIZE, io.DEFAULT_BUFFER_SIZE)
b = _io.BytesIO(b"line one\nline two\n")
t = _io.TextIOWrapper(b, encoding="utf-8")
print(repr(t.readline()), t.encoding)
s = _io.StringIO("x\r\ny")
print(repr(s.read()))
d = _io.IncrementalNewlineDecoder(None, True)
print(repr(d.decode("p\r\nq\r")), repr(d.decode("\n", True)), repr(d.newlines))
print(_io.text_encoding("latin-1"), _io.text_encoding("utf-8", 3), _io.text_encoding(None) in ("utf-8", "locale"))
print(io.text_encoding(None) == _io.text_encoding(None))

where = tempfile.mkdtemp()
with _io.open(where + "/f.txt", "w", encoding="utf-8") as f:
    f.write("text\n")
with io.open(where + "/f.txt", encoding="utf-8") as g:
    print(repr(g.read()))
try:
    raise _io.BlockingIOError(11, "Resource temporarily unavailable")
except io.BlockingIOError as e:
    print("BlockingIOError", e)
try:
    raise BlockingIOError(11, "x")
except _io.BlockingIOError as e:
    print("the builtin's", e)
import os
os.remove(where + "/f.txt")
os.rmdir(where)
