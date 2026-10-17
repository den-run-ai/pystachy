# Documented deviations of lib/io.py's TextIOWrapper (lib/compatibility.md): an encoding other than
# UTF-8, Latin-1 and ASCII raises NotImplementedError, where CPython uses its codec (or raises
# LookupError for a name it does not know); a wrapper the program drops with text waiting is not
# flushed and closed, as CPython's finalizer does at del (__del__ never runs); and newlines, once
# more than one kind of newline has been read, is CPython's tuple of them (here ('\r', '\n')),
# which a str | None cannot hold: it raises NotImplementedError.
from io import TextIOWrapper


class Raw:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False
        self.out = b""

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def read1(self, n: int) -> bytes:
        b = self.data[:n]
        self.data = self.data[n:]
        return b

    def read(self, n: int = -1) -> bytes:
        b = self.data
        self.data = b""
        return b

    def write(self, b: bytes) -> int:
        self.out += b
        return len(b)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


for enc in ["utf-16", "cp1252", "bogus"]:
    try:
        TextIOWrapper(Raw(b""), encoding=enc)
        print(enc, "ok")
    except (NotImplementedError, LookupError) as e:
        print(enc, type(e).__name__, e)
raw = Raw(b"")
t = TextIOWrapper(raw, encoding="ascii")
t.write("waiting")
del t
print(raw.out, raw.closed)
t2 = TextIOWrapper(Raw(b"a\rb\nc"), encoding="ascii")
print(repr(t2.read()))
print(t2.newlines)
