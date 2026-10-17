# lib/io.py: Pystachy's io.TextIOWrapper, against CPython's (Modules/_io/textio.c), over binary
# file objects of the test's own. Raw's read1() gives at most chunk bytes, as a BufferedReader of
# that buffer size does; with log, Raw prints each call the wrapper makes. Plain has no read1(),
# Reader no write() or tell(). Cases after CPython's Lib/test/test_io.py (TextIOWrapperTest).
# Every wrapper is closed before the program drops it: CPython's would close itself then.
from io import TextIOWrapper


class Raw:
    def __init__(self, data: bytes = b"", chunk: int = 8192, log: bool = False, readable: bool = True,
                 writable: bool = True, seekable: bool = False) -> None:
        self.data = data
        self.pos = 0
        self.chunk = chunk
        self.log = log
        self.r = readable
        self.w = writable
        self.s = seekable
        self.closed = False
        self.out = b""
        self.fail = False

    def readable(self) -> bool:
        if self.log:
            print("  readable()")
        return self.r

    def writable(self) -> bool:
        if self.log:
            print("  writable()")
        return self.w

    def seekable(self) -> bool:
        if self.log:
            print("  seekable()")
        return self.s

    def tell(self) -> int:
        if self.log:
            print("  tell()")
        return self.pos

    def read1(self, n: int = -1) -> bytes:
        k = len(self.data) - self.pos if n < 0 else n
        b = self.data[self.pos:self.pos + min(k, self.chunk)]
        self.pos += len(b)
        if self.log:
            print(f"  read1({n}) -> " + (repr(b) if len(b) <= 40 else f"{len(b)} bytes"))
        return b

    def read(self, n: int = -1) -> bytes:
        b = self.data[self.pos:] if n < 0 else self.data[self.pos:self.pos + n]
        self.pos += len(b)
        if self.log:
            print(f"  read({n}) -> " + (repr(b) if len(b) <= 40 else f"{len(b)} bytes"))
        return b

    def write(self, b: bytes) -> int:
        if self.log:
            print(f"  write({b!r})" if len(b) <= 40 else f"  write({len(b)} bytes)")
        if self.fail:
            raise OSError(28, "No space left on device")
        self.out += b
        return len(b)

    def flush(self) -> None:
        if self.log:
            print("  flush()")

    def close(self) -> None:
        if self.log:
            print("  close()")
        self.closed = True

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        return 7


class Plain:
    # no read1(): the wrapper reads chunks with read()
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.closed = False
        self.name = "plain.txt"

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def read(self, n: int = -1) -> bytes:
        b = self.data[self.pos:] if n < 0 else self.data[self.pos:self.pos + n]
        self.pos += len(b)
        print(f"  Plain.read({n}) -> {len(b)} bytes")
        return b

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class Watched:
    # closed is a property, which says when the wrapper reads it
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.log = True
        self.shut = False

    @property
    def closed(self) -> bool:
        if self.log:
            print("  closed?")
        return self.shut

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
        print("  write", b)
        return len(b)

    def flush(self) -> None:
        print("  flush")

    def close(self) -> None:
        print("  close")
        self.shut = True


def emit(t: TextIOWrapper, text: str) -> int:
    return t.write(text)


class Reader:
    # readable only, without write() or tell()
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return True

    def read1(self, n: int) -> bytes:
        b = self.data[:n]
        self.data = self.data[n:]
        return b

    def read(self, n: int = -1) -> bytes:
        b = self.data
        self.data = b""
        return b

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


print("-- the constructor's calls, attributes, repr()")
for r, w, s in [(True, True, False), (True, False, True), (False, True, True), (True, True, True)]:
    raw = Raw(log=True, readable=r, writable=w, seekable=s)
    t = TextIOWrapper(raw, encoding="utf-8")
    print(repr(t), t.encoding, t.errors, t.line_buffering, t.write_through, t.buffer is raw, t.closed, t.newlines)
    print(t.readable(), t.writable(), t.seekable(), t.isatty(), t.fileno())
    t.close()
t = TextIOWrapper(Raw(), "latin-1", "replace", "\r\n", True, True)
print(repr(t), t.encoding, t.errors, t.line_buffering, t.write_through, str(t))
t.close()
p = TextIOWrapper(Plain(b"x"), encoding="ascii")
print(repr(p), p.name, [p])
p.close()
t = TextIOWrapper(Raw(b"caf\xc3\xa9"))
print(t.encoding in ("utf-8", "UTF-8"), t.errors, repr(t.read()))
t.close()
t = TextIOWrapper(Raw(b"caf\xc3\xa9"), encoding="locale")
print(t.encoding, repr(t.read()))
t.close()
for enc in ["utf-8", "UTF8", "u8", "utf_8", "latin-1", "ISO-8859-1", "L1", "iso8859_1", "ascii", "US-ASCII", "646"]:
    t = TextIOWrapper(Raw(b"caf\xc3\xa9\n"), encoding=enc, errors="replace")
    print(repr(enc), repr(t.read()), t.encoding)
    t.close()
for bad in ["x", "\n\r", "\0", " "]:
    try:
        TextIOWrapper(Raw(log=True), encoding="utf-8", newline=bad)
    except ValueError as e:
        print("ValueError:", e)
for enc in ["utf\0-8"]:
    try:
        TextIOWrapper(Raw(log=True), encoding=enc)
    except ValueError as e:
        print("ValueError:", e)
try:
    TextIOWrapper(Raw(log=True), encoding="utf-8", errors="st\0rict")
except ValueError as e:
    print("ValueError:", e)
try:
    TextIOWrapper(Raw(log=True), encoding="bogus", newline="bad")  # (the newline is checked first)
except ValueError as e:
    print("ValueError:", e)

print("-- reading lines in each newline mode, in chunks of 1 to 9 bytes")
MODES: list[str | None] = [None, "", "\n", "\r\n", "\r"]
lines = ["unix\n", "windows\r\n", "os9\r", "last\n", "nonl"]
for enc in ["utf-8", "latin-1"]:
    data = "".join(lines).encode(enc)
    for nl in MODES:
        seen: list[str] = []
        for chunk in range(1, 10):
            t = TextIOWrapper(Raw(data, chunk), encoding=enc, newline=nl)
            got = list(t)
            t.close()
            t = TextIOWrapper(Raw(data, chunk), encoding=enc, newline=nl)
            pairs: list[str] = []
            while True:
                c2 = t.read(2)
                if c2 == "":
                    break
                pairs.append(c2 + t.readline())
            t.close()
            got_s = repr(got) + " " + repr(pairs)
            if got_s not in seen:
                seen.append(got_s)
        print(enc, repr(nl), seen)
data = b"AAA\nBB\x00B\nCCC\rDDD\rEEE\r\nFFF\r\nGGG"
for nl in MODES:
    t = TextIOWrapper(Raw(data, 4), encoding="ascii", newline=nl)
    print(repr(nl), t.readlines())
    t.close()
    t = TextIOWrapper(Raw(data, 5), encoding="ascii", newline=nl)
    print(repr(nl), repr(t.read()))
    t.close()

print("-- read(n) and readline(n) count characters; the chunks they ask for")
t = TextIOWrapper(Raw("aé€😀b\ncd€\n".encode(), log=True), encoding="utf-8")
print(repr(t.read(2)), repr(t.read(2)), repr(t.readline(1)), repr(t.readline(0)), repr(t.readline(2)), repr(t.readline(9)))
print(repr(t.read(0)), repr(t.read(5)), repr(t.read(None)), repr(t.read(-3)), repr(t.readline()))
t.close()
t = TextIOWrapper(Raw(b"x" * 20000, log=True), encoding="ascii")
print(len(t.read(10000)), len(t.read(9000)), len(t.read(1)), len(t.read()))
t.close()
t = TextIOWrapper(Raw("é".encode() * 6000, log=True), encoding="utf-8")
print(t.read(5000) == "é" * 5000, t.read(4000) == "é" * 1000, t.read(10000) == "")  # (len() counts bytes in Pystachy)
t.close()
for chunk in range(1, 6):
    t = TextIOWrapper(Raw("é€😀\n€".encode(), chunk), encoding="utf-8")
    print(chunk, repr(t.read(1)), repr(t.readline()), repr(t.read(1)), repr(t.read()))
    t.close()
t = TextIOWrapper(Raw(b"ab\ncd\nef\ngh\n", log=True), encoding="ascii")
print(t.readline(0) == "", t.readlines(1), t.readlines(3), t.readlines(None), t.readlines())
t.close()
t = TextIOWrapper(Raw("€\n€\n€\n".encode()), encoding="utf-8")
print(t.readlines(2))
t.close()
t = TextIOWrapper(Raw(b"one\r\ntwo\r\nthree", 3), encoding="ascii", newline="\r\n")
print(repr(t.readline(4)), repr(t.readline(1)), repr(t.readline()), repr(t.readline()), repr(t.readline()))
t.close()

print("-- newlines: the kind of newline read")
CASES: list[tuple[bytes, str | None]] = [(b"a\nb\n", None), (b"a\r\nb\r\n", None), (b"a\rb\r", None), (b"a\r\nb", ""), (b"a\nb", "\n"), (b"x", None)]
for data, nl in CASES:
    t = TextIOWrapper(Raw(data, 1), encoding="ascii", newline=nl)
    before = t.newlines
    first = t.readline()
    print(repr(data), repr(nl), before, repr(first), repr(t.newlines), repr(t.read()), repr(t.newlines))
    t.close()

print("-- decoding errors")
for errors in ["strict", "replace", "ignore", "surrogateescape", "backslashreplace"]:
    for data in [b"ab\xffcd", b"ab\xe2\x82", b"\xe2\x82(xy", b"ok\xed\xa0\x80"]:
        for chunk in [1, 2, 8192]:
            t = TextIOWrapper(Raw(data, chunk), encoding="utf-8", errors=errors)
            try:
                print(errors, repr(data), chunk, repr(t.read(1)), ascii(t.read()))
            except UnicodeDecodeError as e:
                print(errors, repr(data), chunk, "UnicodeDecodeError:", e)
            t.close()
t = TextIOWrapper(Raw(b"abc\n\xff\n"), encoding="ascii")
try:
    t.read()
except UnicodeDecodeError as e:
    print("UnicodeDecodeError:", e)
t.close()
t = TextIOWrapper(Raw(b"abc\n\xff\n"), encoding="ascii", errors="replace")
print(repr(t.read()))
t.close()

print("-- writing: counts, newline translation, buffering")
for nl in MODES:
    raw = Raw()
    t = TextIOWrapper(raw, encoding="ascii", newline=nl)
    print(repr(nl), t.write("AAA\nB"), t.write("BB\nCCC\n"), t.write("X\rY\r\nZ"), raw.out)
    t.flush()
    print(raw.out, raw.closed)
    t.close()
raw = Raw(log=True)
t = TextIOWrapper(raw, encoding="utf-8")
print(t.write("aé€😀"), t.write(""), t.write("x" * 8000))
print(t.write("y" * 191), t.write("z"), len(raw.out))
print(t.write("w" * 10000), len(raw.out))
t.writelines(["1\n", "2\n"])
t.writelines(("3", "4"))
t.flush()
print(len(raw.out), raw.out[-8:])
t.close()
print("line_buffering")
raw = Raw(log=True)
t = TextIOWrapper(raw, encoding="utf-8", newline="\n", line_buffering=True)
t.write("X")
t.write("Y\nZ")
t.write("A\rB")
t.write("C")
print(raw.out)
t.close()
print("write_through")
raw = Raw(log=True)
t = TextIOWrapper(raw, encoding="utf-8", newline="\r\n", write_through=True)
t.write("a\nb")
t.write("")
t.write("c")
print(raw.out)
t.close()
print("print()")
raw = Raw(log=True)
t = TextIOWrapper(raw, encoding="latin-1", newline="\r", line_buffering=True)
print("é", 1, 2.5, sep="-", end="!\n", file=t)
print("no newline", end="", file=t, flush=True)
t.close()
print(raw.out)

print("-- encoding errors")
for enc, errors, text in [("latin-1", "strict", "a€b"), ("latin-1", "replace", "a€b"), ("ascii", "strict", "é"),
                          ("ascii", "backslashreplace", "é€"), ("ascii", "xmlcharrefreplace", "é€"),
                          ("utf-8", "strict", "x\udc80"), ("utf-8", "surrogateescape", "x\udc80"),
                          ("utf-8", "surrogatepass", "x\udc80")]:
    raw = Raw()
    t = TextIOWrapper(raw, encoding=enc, errors=errors, newline="\r\n")
    try:
        print(enc, errors, t.write("\n" + text), end=" ")
        t.flush()
        print(raw.out)
    except UnicodeEncodeError as e:
        print("UnicodeEncodeError:", e)
    t.close()

print("-- reads and writes on one wrapper")
raw = Raw(b"abc\r", 4, log=True)
t = TextIOWrapper(raw, encoding="ascii")
print(repr(t.read(1)), t.write("X"), repr(t.read(1)), repr(t.read()), raw.out)
t.close()
raw = Raw(b"a\r\nb", 2, log=True)
t = TextIOWrapper(raw, encoding="ascii")
print(repr(t.read(1)), t.write("Y"), repr(t.read()), raw.out)
t.close()
raw = Raw(b"a\nb\n", 1)
t = TextIOWrapper(raw, encoding="ascii")
print(repr(t.readline()), t.newlines, t.write("Z"), t.newlines, repr(t.readline()), t.newlines)
t.close()
raw = Raw(b"line1\nline2\nline3\n", 8, log=True, seekable=True)
t = TextIOWrapper(raw, encoding="ascii")
print(repr(t.readline()), t.write("W"), repr(t.readline()), repr(t.read()), raw.out)
t.close()
raw = Raw(b"l1\nl2\nl3\n", 3, log=True, seekable=True)
t = TextIOWrapper(raw, encoding="ascii")
print(repr(next(t)), t.write("V"), repr(next(t)))
t.flush()
print(repr(t.readline()), t.write("U"), repr(t.read()), raw.out)
t.close()

print("-- closing")
raw = Raw(b"data", log=True)
t = TextIOWrapper(raw, encoding="ascii")
t.write("pending")
t.close()
t.close()
print(raw.closed, t.closed, raw.out)
for what in ["read", "readline", "write", "flush", "iter", "next", "writelines", "readlines", "with"]:
    try:
        if what == "read":
            t.read()
        elif what == "readline":
            t.readline()
        elif what == "write":
            t.write("x")
        elif what == "flush":
            t.flush()
        elif what == "iter":
            iter(t)
        elif what == "next":
            next(t)
        elif what == "writelines":
            t.writelines(["x"])
        elif what == "readlines":
            t.readlines()
        else:
            with t:
                pass
    except ValueError as e:
        print(what, "ValueError:", e)
raw = Raw(b"x")
t = TextIOWrapper(raw, encoding="ascii")
raw.close()
print(t.closed)
t.close()
raw = Raw(log=True)
t = TextIOWrapper(raw, encoding="ascii")
t.write("lost")
raw.fail = True
try:
    t.close()
except OSError as e:
    print("OSError:", e)
print(raw.closed, t.closed)
raw = Raw(b"in", log=True)
with TextIOWrapper(raw, encoding="ascii") as t:
    print(repr(t.read()), t.write("out"))
print(raw.closed, raw.out)

print("-- unsupported operations")
raw = Raw(b"abc", readable=False)
t = TextIOWrapper(raw, encoding="ascii")
for what in ["read", "read(1)", "readline", "next", "readlines"]:
    try:
        if what == "read":
            t.read()
        elif what == "read(1)":
            t.read(1)
        elif what == "readline":
            t.readline()
        elif what == "next":
            next(t)
        else:
            t.readlines()
    except OSError as e:
        print(what, type(e).__name__, e, isinstance(e, ValueError))
print(t.newlines)
t.close()
raw = Raw(b"abc", writable=False)
t = TextIOWrapper(raw, encoding="ascii")
try:
    t.write("x")
except ValueError as e:
    print("write", type(e).__name__, e, isinstance(e, OSError))
t.close()
for name in ["encoding", "errors", "line_buffering", "write_through", "closed", "newlines", "buffer", "name"]:
    pw = TextIOWrapper(Plain(b""), encoding="ascii")
    try:
        if name == "encoding":
            pw.encoding = "x"
        elif name == "errors":
            pw.errors = "x"
        elif name == "line_buffering":
            pw.line_buffering = True
        elif name == "write_through":
            pw.write_through = True
        elif name == "closed":
            pw.closed = True
        elif name == "newlines":
            pw.newlines = "\n"
        elif name == "buffer":
            pw.buffer = Plain(b"")
        else:
            pw.name = "x"
    except AttributeError as e:
        print(name, "AttributeError:", e)
    pw.close()

print("-- a buffer without read1(), and one without write() or tell()")
p = TextIOWrapper(Plain(b"first\nsecond\n" * 700), encoding="ascii")
print(repr(p.readline()), len(p.read(9000)), len(p.read()))
p.close()
q = TextIOWrapper(Reader(b"r1\nr2\n"), encoding="utf-8")
print(q.readlines(), q.seekable(), q.writable())
try:
    q.write("x")
except OSError as e:
    print(type(e).__name__, e)
q.close()
print(q.closed)

print("-- the reads of the buffer's closed attribute")
wb = Watched(b"a\nb\nc\n")
wt = TextIOWrapper(wb, encoding="ascii")
print("readline", repr(wt.readline()))
print("write", emit(wt, "x"))
print("next", repr(next(wt)))
print("writelines")
wt.writelines(["y", "z"])
print("flush")
wt.flush()
print("readlines", wt.readlines())
print("read", repr(wt.read(1)), repr(wt.read()))
print("closed", wt.closed)
print("close")
wt.close()
print("close again")
wt.close()
wb.log = False
