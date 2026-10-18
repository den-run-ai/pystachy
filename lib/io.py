"""The io module's in-memory streams, StringIO and BytesIO, written for Pystachy.

CPython's io is a C module (Modules/_io); this one has StringIO, after Modules/_io/stringio.c of
CPython 3.13.16: the same reads, writes, seeks, newline translation and errors, on a str buffer
(lib/README.md). Positions and sizes count a str's bytes past ASCII, as len() and slicing do.
BytesIO follows Modules/_io/bytesio.c in the same way, on a bytes buffer.
TextIOWrapper, after Modules/_io/textio.c, is the text layer over a binary stream; its sizes count
characters, as CPython's do.
"""

from typing import Self

__all__ = ["StringIO", "BytesIO", "TextIOWrapper", "SEEK_SET", "SEEK_CUR", "SEEK_END"]

SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2
# the largest Py_ssize_t (PY_SSIZE_T_MAX), which bounds BytesIO's positions and size
_SSIZE_MAX = 9223372036854775807


class StringIO:
    """Text I/O implementation using an in-memory buffer.

    The initial_value argument sets the value of object.  The newline
    argument is like the one of TextIOWrapper's constructor.
    """

    def __init__(self, initial_value: str | None = "", newline: str | None = "\n") -> None:
        if newline is not None and newline != "" and newline != "\n" and newline != "\r" and newline != "\r\n":
            raise ValueError(f"illegal newline value: {newline!r}")
        # newline None: \r\n and \r are written as \n; "": nothing is translated, and \n, \r and
        # \r\n end lines; "\r" or "\r\n": each \n written is written as it; "\n": nothing at all
        self._newline = newline
        self._buf = ""  # the text, but for _tail
        self._tail: list[str] = []  # what was written at the end since _buf was last joined
        self._size = 0  # the length of the text: of _buf and _tail
        self._pos = 0
        self.closed = False
        self.line_buffering = False
        self.encoding: str | None = None
        self.errors: str | None = None
        if initial_value is not None and initial_value != "":
            self.write(initial_value)
            self._pos = 0

    def _check(self) -> None:
        if self.closed:
            raise ValueError("I/O operation on closed file")

    def _check_base(self) -> None:
        # (the methods StringIO has from IOBase say it with a full stop)
        if self.closed:
            raise ValueError("I/O operation on closed file.")

    def _join(self) -> None:
        if self._tail:
            self._buf = self._buf + "".join(self._tail)
            self._tail = []

    def getvalue(self) -> str:
        """Retrieve the entire contents of the object."""
        self._check()
        self._join()
        return self._buf

    def write(self, s: str) -> int:
        """Write string to file.

        Returns the number of characters written, which is always equal to
        the length of the string.
        """
        self._check()
        n = len(s)
        if self._newline is None:
            s = s.replace("\r\n", "\n").replace("\r", "\n")
        elif self._newline == "\r" or self._newline == "\r\n":
            s = s.replace("\n", self._newline)
        if s == "":
            return n
        if self._pos == self._size:
            self._tail.append(s)
        else:
            self._join()
            if self._pos > self._size:
                # a write past the end pads the gap with NULs
                self._buf = self._buf + "\0" * (self._pos - self._size)
                self._size = self._pos
            self._buf = self._buf[:self._pos] + s + self._buf[self._pos + len(s):]
        self._pos += len(s)
        if self._pos > self._size:
            self._size = self._pos
        return n

    def writelines(self, lines: list[str]) -> None:
        """Write a list of lines to stream."""
        self._check_base()
        for line in lines:
            self.write(line)

    def read(self, size: int | None = -1) -> str:
        """Read at most size characters, returned as a string.

        If the argument is negative or omitted, read until EOF
        is reached. Return an empty string at EOF.
        """
        self._check()
        self._join()
        n = self._size - self._pos
        if size is not None and 0 <= size < n:
            n = size
        if n <= 0:
            return ""
        start = self._pos
        self._pos += n
        return self._buf[start:self._pos]

    def readline(self, size: int | None = -1) -> str:
        """Read until newline or EOF.

        Returns an empty string if EOF is hit immediately.
        """
        self._check()
        self._join()
        start = self._pos
        if start >= self._size:
            return ""
        limit = self._size - start
        if size is not None and 0 <= size < limit:
            limit = size
        stop = start + limit
        buf = self._buf
        end = -1
        if self._newline is None or self._newline == "\n":
            i = buf.find("\n", start, stop)
            if i >= 0:
                end = i + 1
        elif self._newline == "":
            # the first \n, \r or \r\n (a \r at the limit ends the line)
            i = buf.find("\n", start, stop)
            j = buf.find("\r", start, i if i >= 0 else stop)
            if j >= 0:
                end = j + 2 if j + 1 < stop and buf[j + 1] == "\n" else j + 1
            elif i >= 0:
                end = i + 1
        else:
            i = buf.find(self._newline, start, stop)
            if i >= 0:
                end = i + len(self._newline)
        if end < 0:
            end = stop
        self._pos = end
        return buf[start:end]

    def readlines(self, hint: int | None = -1) -> list[str]:
        """Return a list of lines from the stream.

        hint can be specified to control the number of lines read: no more
        lines will be read if the total size (in bytes/characters) of all
        lines so far exceeds hint.
        """
        self._check_base()
        lines: list[str] = []
        total = 0
        while True:
            line = self.readline()
            if line == "":
                break
            lines.append(line)
            total += len(line)
            if hint is not None and 0 < hint < total:
                break
        return lines

    def __iter__(self) -> Self:
        self._check_base()
        return self

    def __enter__(self):  # (compiled only where a with statement calls it, as __exit__ is)
        """Context management protocol.  Returns self (an instance of IOBase)."""
        self._check_base()
        return self

    def __exit__(self, *args) -> None:
        """Context management protocol.  Calls close()"""
        self.close()

    def __next__(self) -> str:
        line = self.readline()
        if line == "":
            raise StopIteration
        return line

    def tell(self) -> int:
        """Tell the current file position."""
        self._check()
        return self._pos

    def seek(self, pos: int, whence: int = 0) -> int:
        """Change stream position.

        Seek to character offset pos relative to position indicated by whence:
            0  Start of stream (the default).  pos should be >= 0;
            1  Current position - pos must be 0;
            2  End of stream - pos must be 0.
        Returns the new absolute position.
        """
        self._check()
        if whence != 0 and whence != 1 and whence != 2:
            raise ValueError(f"Invalid whence ({whence}, should be 0, 1 or 2)")
        if pos < 0 and whence == 0:
            raise ValueError(f"Negative seek position {pos}")
        if whence != 0 and pos != 0:
            raise OSError("Can't do nonzero cur-relative seeks")
        if whence == 1:
            pos = self._pos
        elif whence == 2:
            pos = self._size
        self._pos = pos
        return pos

    def truncate(self, pos: int | None = None) -> int:
        """Truncate size to pos.

        The pos argument defaults to the current file position, as
        returned by tell().  The current file position is unchanged.
        Returns the new absolute position.
        """
        self._check()
        size = self._pos if pos is None else pos
        if size < 0:
            raise ValueError(f"Negative size value {size}")
        if size < self._size:
            self._join()
            self._buf = self._buf[:size]
            self._size = size
        return size

    def close(self) -> None:
        """Close the IO object.

        Attempting any further operation after the object is closed
        will raise a ValueError.

        This method has no effect if the file is already closed.
        """
        self.closed = True
        self._buf = ""
        self._tail = []

    def flush(self) -> None:
        """Does nothing: a StringIO has no buffer to write out."""

    def readable(self) -> bool:
        """Returns True if the IO object can be read."""
        self._check()
        return True

    def writable(self) -> bool:
        """Returns True if the IO object can be written."""
        self._check()
        return True

    def seekable(self) -> bool:
        """Returns True if the IO object can be seeked."""
        self._check()
        return True

    def isatty(self) -> bool:
        """Return whether this is an 'interactive' stream."""
        self._check_base()
        return False


class BytesIO:
    """Buffered I/O implementation using an in-memory bytes buffer."""

    def __init__(self, initial_bytes: bytes | None = None) -> None:
        # (CPython's default is no argument, as None is.) __init__ may be called again: with bytes,
        # the object holds them, open; without, it is emptied, and a closed one stays closed
        self._buf = b"" if initial_bytes is None else initial_bytes  # the bytes, but for _tail
        self._tail: list[bytes] = []  # what was written at the end since _buf was last joined
        self._size = len(self._buf)  # the length of the bytes: of _buf and _tail
        self._pos = 0
        if initial_bytes is not None or not hasattr(self, "_closed"):
            self._closed = False

    def _check(self) -> None:
        if self._closed:
            raise ValueError("I/O operation on closed file.")

    def _join(self) -> None:
        if self._tail:
            self._buf = self._buf + b"".join(self._tail)
            self._tail = []

    def _line(self, size: int) -> bytes:
        # the next line, of at most size bytes if size >= 0 (scan_eol, then read_bytes)
        start = self._pos
        n = self._size - start
        if 0 <= size < n:
            n = size
        if n <= 0:
            return b""
        self._join()
        i = self._buf.find(b"\n", start, start + n)
        if i >= 0:
            n = i + 1 - start
        self._pos = start + n
        return self._buf[start:self._pos]

    @property
    def closed(self) -> bool:
        """True if the file is closed."""
        return self._closed

    @closed.setter
    def closed(self, value: object) -> None:
        # (an attribute of the C type that has no setter)
        raise AttributeError("attribute 'closed' of '_io.BytesIO' objects is not writable")

    def readable(self) -> bool:
        """Returns True if the IO object can be read."""
        self._check()
        return True

    def writable(self) -> bool:
        """Returns True if the IO object can be written."""
        self._check()
        return True

    def seekable(self) -> bool:
        """Returns True if the IO object can be seeked."""
        self._check()
        return True

    def flush(self) -> None:
        """Does nothing."""
        self._check()

    def getvalue(self) -> bytes:
        """Retrieve the entire contents of the BytesIO object."""
        self._check()
        self._join()
        return self._buf

    def isatty(self) -> bool:
        """Always returns False.

        BytesIO objects are not connected to a TTY-like device."""
        self._check()
        return False

    def tell(self) -> int:
        """Current file position, an integer."""
        self._check()
        return self._pos

    def read(self, size: int | None = -1, /) -> bytes:
        """Read at most size bytes, returned as a bytes object.

        If the size argument is negative, read until EOF is reached.
        Return an empty bytes object at EOF."""
        self._check()
        n = self._size - self._pos
        if size is not None and 0 <= size < n:
            n = size
        if n <= 0:
            return b""
        self._join()
        start = self._pos
        self._pos += n
        return self._buf[start:self._pos]

    def read1(self, size: int | None = -1, /) -> bytes:
        """Read at most size bytes, returned as a bytes object.

        If the size argument is negative or omitted, read until EOF is
        reached.  Return an empty bytes object at EOF."""
        return self.read(size)

    def readline(self, size: int | None = -1, /) -> bytes:
        """Next line from the file, as a bytes object.

        Retain newline.  A non-negative size argument limits the maximum
        number of bytes to return (an incomplete line may be returned then).
        Return an empty bytes object at EOF."""
        self._check()
        return self._line(-1 if size is None else size)

    def readlines(self, size: int | None = None, /) -> list[bytes]:
        """List of bytes objects, each a line from the file.

        Call readline() repeatedly and return a list of the lines so read.
        The optional size argument, if given, is an approximate bound on the
        total number of bytes in the lines returned."""
        self._check()
        maxsize = -1 if size is None else size
        lines: list[bytes] = []
        total = 0
        while True:
            line = self._line(-1)
            if line == b"":
                break
            lines.append(line)
            total += len(line)
            # (the C type's bound: the lines stop once their total reaches it)
            if maxsize > 0 and total >= maxsize:
                break
        return lines

    def truncate(self, size: int | None = None, /) -> int:
        """Truncate the file to at most size bytes.

        Size defaults to the current file position, as returned by tell().
        The current file position is unchanged.  Returns the new size."""
        self._check()
        n = self._pos if size is None else size
        if n < 0:
            raise ValueError(f"negative size value {n}")
        if n < self._size:
            self._join()
            self._buf = self._buf[:n]
            self._size = n
        return n

    def __iter__(self) -> Self:
        # (the C type's is the object itself, open or closed: its __next__ checks)
        return self

    def __next__(self) -> bytes:
        self._check()
        line = self._line(-1)
        if line == b"":
            raise StopIteration
        return line

    def seek(self, pos: int, whence: int = 0, /) -> int:
        """Change stream position.

        Seek to byte offset pos relative to position indicated by whence:
             0  Start of stream (the default).  pos should be >= 0;
             1  Current position - pos may be negative;
             2  End of stream - pos usually negative.
        Returns the new absolute position."""
        if whence < -2147483648 or whence > 2147483647:
            # (whence is a C int, converted before anything is checked)
            raise OverflowError("Python int too large to convert to C int")
        self._check()
        if pos < 0 and whence == 0:
            raise ValueError(f"negative seek value {pos}")
        if whence == 1:
            if pos > _SSIZE_MAX - self._pos:
                raise OverflowError("new position too large")
            pos += self._pos
        elif whence == 2:
            if pos > _SSIZE_MAX - self._size:
                raise OverflowError("new position too large")
            pos += self._size
        elif whence != 0:
            raise ValueError(f"invalid whence ({whence}, should be 0, 1 or 2)")
        if pos < 0:
            pos = 0
        self._pos = pos
        return pos

    def write(self, b: bytes, /) -> int:
        """Write bytes to file.

        Return the number of bytes written."""
        self._check()
        n = len(b)
        if n == 0:
            return 0
        if self._pos > _SSIZE_MAX - n:
            raise OverflowError("new buffer size too large")
        if self._pos == self._size:
            self._tail.append(b)
        else:
            self._join()
            if self._pos > self._size:
                # a write past the end pads the gap with NUL bytes
                self._buf = self._buf + b"\0" * (self._pos - self._size) + b
            else:
                self._buf = self._buf[:self._pos] + b + self._buf[self._pos + n:]
        self._pos += n
        if self._pos > self._size:
            self._size = self._pos
        return n

    def writelines(self, lines, /) -> None:  # (lines: any iterable of bytes)
        """Write lines to the file.

        Note that newlines are not added.  lines can be any iterable object
        producing bytes-like objects.  This is equivalent to calling write()
        for each element."""
        self._check()
        for line in lines:
            self.write(line)

    def close(self) -> None:
        """Disable all I/O operations."""
        self._closed = True
        self._buf = b""
        self._tail = []

    def __enter__(self):  # (compiled only where a with statement calls it, as __exit__ is)
        self._check()
        return self

    def __exit__(self, *args) -> None:
        self.close()


def _unsupported(message: str) -> None:
    # io.UnsupportedOperation(message), which the runtime raises as it does for a file
    from _pystachy_io import unsupported
    unsupported(message)


def _nchars(s: str, i: int, j: int) -> int:
    # the number of characters of s[i:j], a str holding UTF-8: its bytes that continue no sequence,
    # as the runtime counts them (len() counts bytes)
    n = 0
    while i < j:
        if ord(s[i]) & 0xC0 != 0x80:
            n += 1
        i += 1
    return n


def _skip(s: str, i: int, n: int) -> int:
    # the offset of s n characters after offset i, or its end
    end = len(s)
    while n > 0 and i < end:
        i += 1
        while i < end and ord(s[i]) & 0xC0 == 0x80:
            i += 1
        n -= 1
    return i


def _utf8_tail(data: bytes) -> int:
    # the number of bytes at data's end that begin a UTF-8 sequence without ending it, which the
    # incremental decoder keeps for more data (lib/_pystachy_codecs.py's, after CPython's
    # Objects/stringlib/codecs.h)
    n = len(data)
    for k in range(1, 4):
        if k > n:
            return 0
        c = data[n - k]
        if c & 0xC0 == 0x80:
            continue
        need = 2 if 0xC2 <= c <= 0xDF else 3 if 0xE0 <= c <= 0xEF else 4 if 0xF0 <= c <= 0xF4 else 0
        if need <= k:
            return 0
        if k >= 2:
            c2 = data[n - k + 1]
            if c == 0xED and c2 >= 0xA0 and k == 2:
                return 2  # (a surrogate's first two bytes: truncated, whatever the error handler)
            if (c == 0xE0 and c2 < 0xA0) or (c == 0xED and c2 >= 0xA0) or (c == 0xF0 and c2 < 0x90) or (c == 0xF4 and c2 >= 0x90):
                return 0
        return k
    return 0


def _codec(encoding: str) -> int:
    # the codec an encoding names, as str.encode() finds it (aliases included): 0 UTF-8, 1 Latin-1,
    # 2 ASCII, by what each makes of U+00E9; another, which str.encode() does not have, is an error
    known = True
    try:
        e = "é".encode(encoding, "replace")
    except LookupError:
        known = False
        e = b""
    if not known:
        raise NotImplementedError(f"TextIOWrapper supports only the UTF-8, Latin-1 and ASCII encodings, not '{encoding}'")
    return 0 if len(e) == 2 else 1 if e == b"\xe9" else 2


# The buffer's methods that a TextIOWrapper may not need, called where CPython calls them: an
# object of a class without one raises CPython's AttributeError there (the class decides
# hasattr() as the program compiles)
def _buffer_read1(buffer, size: int) -> bytes:
    # a chunk: read1(), or read() where the buffer has no read1()
    if hasattr(buffer, "read1"):
        return buffer.read1(size)
    if hasattr(buffer, "read"):
        return buffer.read(size)
    raise AttributeError(f"'{type(buffer).__name__}' object has no attribute 'read'")


def _buffer_read(buffer) -> bytes:
    if hasattr(buffer, "read"):
        return buffer.read()
    raise AttributeError(f"'{type(buffer).__name__}' object has no attribute 'read'")


def _buffer_write(buffer, b: bytes) -> None:
    if hasattr(buffer, "write"):
        buffer.write(b)
    else:
        raise AttributeError(f"'{type(buffer).__name__}' object has no attribute 'write'")


def _buffer_tell(buffer) -> bool:
    # is the buffer's position 0
    if hasattr(buffer, "tell"):
        return buffer.tell() == 0
    raise AttributeError(f"'{type(buffer).__name__}' object has no attribute 'tell'")


def _buffer_name(buffer) -> str:
    # " name=" and repr() of the buffer's name, if it has one, for TextIOWrapper's repr()
    if hasattr(buffer, "name"):
        return " name=" + repr(buffer.name)
    return ""


class TextIOWrapper[B]:
    r"""Character and line based layer over a BufferedIOBase object, buffer.

    encoding gives the name of the encoding that the stream will be
    decoded or encoded with. It defaults to locale.getencoding().

    errors determines the strictness of encoding and decoding (see
    help(codecs.Codec) or the documentation for codecs.register) and
    defaults to "strict".

    newline controls how line endings are handled. It can be None, '',
    '\n', '\r', and '\r\n'.  It works as follows:

    * On input, if newline is None, universal newlines mode is
      enabled. Lines in the input can end in '\n', '\r', or '\r\n', and
      these are translated into '\n' before being returned to the
      caller. If it is '', universal newline mode is enabled, but line
      endings are returned to the caller untranslated. If it has any of
      the other legal values, input lines are only terminated by the given
      string, and the line ending is returned to the caller untranslated.

    * On output, if newline is None, any '\n' characters written are
      translated to the system default line separator, os.linesep. If
      newline is '' or '\n', no translation takes place. If newline is any
      of the other legal values, any '\n' characters written are translated
      to the given string.

    If line_buffering is True, a call to flush is implied when a call to
    write contains a newline character.
    """

    # After Modules/_io/textio.c of CPython 3.13.16: the buffer is any object with the methods it
    # calls (each buffer class is a specialization). Reads decode chunks of 8192 bytes (read1(), or
    # read()) into _decoded, which a read takes from; writes encode the text, which waits in
    # _pending until 8192 bytes, a flush, or a newline with line_buffering, go to buffer.write().
    # The decoder is the codec's incremental one (UTF-8's keeps a sequence a chunk ends without
    # completing in _dpending), within IncrementalNewlineDecoder for newline None or "" (a final
    # \r waits in _pendingcr for the \n that may follow; _seennl, the newlines read). Positions in
    # _decoded are offsets of its bytes; the sizes given count characters, as CPython's do.

    def __init__(self, buffer: B, encoding: str | None = None, errors: str | None = None, newline: str | None = None,
                 line_buffering: bool = False, write_through: bool = False) -> None:
        if encoding is not None and "\0" in encoding:
            raise ValueError("embedded null character")
        if newline is not None and "\0" in newline:
            raise ValueError("embedded null character")
        errs = "strict"
        if errors is not None:
            errs = errors
        if "\0" in errs:
            raise ValueError("embedded null character")
        if newline is not None and newline != "" and newline != "\n" and newline != "\r" and newline != "\r\n":
            raise ValueError(f"illegal newline value: {newline}")
        if encoding is None:
            # the runtime's, as a file's (UTF-8 mode's "utf-8" in the C locale, else the locale's)
            from _pystachy_io import default_encoding
            encoding = default_encoding()
        elif encoding == "locale":
            from _pystachy_io import locale_encoding
            encoding = locale_encoding()
        self._codec: int = _codec(encoding)
        self._encoding: str = encoding
        self._errors: str = errs
        self._line_buffering: bool = line_buffering
        self._write_through: bool = write_through
        self._readuniversal: bool = newline is None or newline == ""
        self._readtranslate: bool = newline is None
        self._readnl: str = "" if newline is None else newline
        # what a \n written becomes, where it is not itself (newline None writes os.linesep, POSIX's \n)
        self._writenl: str = "\r" if newline == "\r" else "\r\n" if newline == "\r\n" else ""
        self._buffer = buffer
        self._decoded: str = ""  # decoded_chars: what reads take from, from _used on
        self._used: int = 0
        self._dascii: bool = True  # (_decoded is ASCII: an offset is its characters' count)
        self._dpending: bytes = b""  # the UTF-8 decoder's bytes of an incomplete sequence
        self._pendingcr: bool = False
        self._seennl: int = 0  # 1 \r, 2 \n, 4 \r\n
        self._pending: list[bytes] = []  # pending_bytes, of _pending_count bytes
        self._pending_count: int = 0
        self._b2cratio: float = 0.0
        self._snapshot: bool = False  # (CPython keeps one for tell() after a read while telling)
        self._readable: bool = buffer.readable()  # a decoder
        self._writable: bool = buffer.writable()  # an encoder
        self._seekable: bool = buffer.seekable()
        self._telling: bool = self._seekable
        if self._seekable and self._writable:
            # (_textiowrapper_fix_encoder_state: no codec here has a state to set, as UTF-16's BOM)
            _buffer_tell(buffer)

    @property
    def encoding(self) -> str:
        return self._encoding

    @encoding.setter
    def encoding(self, value: object) -> None:
        raise AttributeError("readonly attribute")

    @property
    def errors(self) -> str:
        return self._errors

    @errors.setter
    def errors(self, value: object) -> None:
        raise AttributeError("attribute 'errors' of '_io.TextIOWrapper' objects is not writable")

    @property
    def line_buffering(self) -> bool:
        return self._line_buffering

    @line_buffering.setter
    def line_buffering(self, value: object) -> None:
        raise AttributeError("readonly attribute")

    @property
    def write_through(self) -> bool:
        return self._write_through

    @write_through.setter
    def write_through(self, value: object) -> None:
        raise AttributeError("readonly attribute")

    @property
    def buffer(self) -> B:
        return self._buffer

    @buffer.setter
    def buffer(self, value: object) -> None:
        raise AttributeError("readonly attribute")

    @property
    def closed(self) -> bool:
        return self._buffer.closed

    @closed.setter
    def closed(self, value: object) -> None:
        raise AttributeError("attribute 'closed' of '_io.TextIOWrapper' objects is not writable")

    @property
    def name(self) -> str:
        return self._buffer.name

    @name.setter
    def name(self, value: object) -> None:
        raise AttributeError("attribute 'name' of '_io.TextIOWrapper' objects is not writable")

    @property
    def newlines(self) -> str | None:
        # IncrementalNewlineDecoder's: the newlines read (but where a write reset the decoder)
        if not self._readable or not self._readuniversal or self._seennl == 0:
            return None
        if self._seennl == 1:
            return "\r"
        if self._seennl == 2:
            return "\n"
        if self._seennl == 4:
            return "\r\n"
        raise NotImplementedError("TextIOWrapper.newlines is a tuple once more than one kind of newline has been read, which is not supported")

    @newlines.setter
    def newlines(self, value: object) -> None:
        raise AttributeError("attribute 'newlines' of '_io.TextIOWrapper' objects is not writable")

    def __repr__(self) -> str:
        return f"<_io.TextIOWrapper{_buffer_name(self._buffer)} encoding={self._encoding!r}>"

    def _check_closed(self) -> None:
        if self._buffer.closed:
            raise ValueError("I/O operation on closed file.")

    def _set_decoded(self, s: str) -> None:
        self._decoded = s
        self._used = 0
        self._dascii = s.isascii()

    def _take(self, n: int) -> str:
        # textiowrapper_get_decoded_chars: n characters of _decoded (n < 0: all that is left)
        d = self._decoded
        start = self._used
        if n < 0 or start + n >= len(d):
            end = len(d)
        elif self._dascii:
            end = start + n
        else:
            end = _skip(d, start, n)
        self._used = end
        return d if start == 0 and end == len(d) else d[start:end]

    def _decode(self, data: bytes, final: bool) -> str:
        # the codec's incremental decoder (UTF-8's: codecs.utf_8_decode of the bytes it kept and
        # these), within IncrementalNewlineDecoder's decode() for newline None or ""
        if self._codec == 0:
            data = self._dpending + data
            used = len(data) if final else len(data) - _utf8_tail(data)
            if used == len(data):
                text = data.decode("utf-8", self._errors)
            else:
                # the bytes before the tail, where a sequence they end without completing is one
                # that the tail's first byte interrupts: a NUL interrupts it as that byte does,
                # and is one more character, dropped (lib/_pystachy_codecs.py's utf_8_decode)
                text = (data[:used] + b"\x00").decode("utf-8", self._errors)[:-1]
            self._dpending = data[used:]
        else:
            text = data.decode("latin-1" if self._codec == 1 else "ascii", self._errors)
        if not self._readuniversal:
            return text
        if self._pendingcr and (final or text != ""):
            text = "\r" + text
            self._pendingcr = False
        if not final and text.endswith("\r"):
            # (a \r is kept for the next pass, so that readline() gets a \r\n whole)
            text = text[:-1]
            self._pendingcr = True
        if text == "":
            return text
        seen = self._seennl
        crlf = "\r\n" in text
        if crlf:
            seen |= 4
        if "\r" in text:
            single = text.replace("\r\n", "") if crlf else text
            if "\r" in single:
                seen |= 1
            if "\n" in single:
                seen |= 2
            if self._readtranslate:
                text = text.replace("\r\n", "\n").replace("\r", "\n")
        elif "\n" in text:
            seen |= 2
        self._seennl = seen
        return text

    def _reset_decoder(self) -> None:
        # decoder.reset(): it forgets a pending sequence, \r and the newlines read
        self._dpending = b""
        self._pendingcr = False
        self._seennl = 0

    def _read_chunk(self, size_hint: int) -> bool:
        # textiowrapper_read_chunk: decode the next chunk of the buffer into _decoded; False at
        # its end
        if not self._readable:
            _unsupported("not readable")
        if size_hint > 0:
            hint = max(self._b2cratio, 1.0) * size_hint
            # (CPython's C conversion of a double past the range of a Py_ssize_t gives its least)
            size_hint = int(hint) if hint < 9.2233720368547758e18 else 0
        data = _buffer_read1(self._buffer, max(8192, size_hint))
        nbytes = len(data)
        decoded = self._decode(data, nbytes == 0)
        self._set_decoded(decoded)
        nchars = len(decoded) if self._dascii else _nchars(decoded, 0, len(decoded))
        self._b2cratio = nbytes / nchars if nchars > 0 else 0.0
        if self._telling:
            self._snapshot = True
        return nbytes > 0 or nchars > 0

    def _writeflush(self) -> None:
        # _textiowrapper_writeflush: the pending bytes to buffer.write(), at once
        if len(self._pending) == 0:
            return
        b = self._pending[0] if len(self._pending) == 1 else b"".join(self._pending)
        self._pending = []
        self._pending_count = 0
        _buffer_write(self._buffer, b)

    def write(self, text: str, /) -> int:
        self._check_closed()
        if not self._writable:
            _unsupported("not writable")
        n = len(text) if text.isascii() else _nchars(text, 0, len(text))
        haslf = (self._writenl != "" or self._line_buffering) and "\n" in text
        if haslf and self._writenl != "":
            text = text.replace("\n", self._writenl)
        needflush = self._line_buffering and (haslf or "\r" in text)
        b = text.encode("utf-8" if self._codec == 0 else "latin-1" if self._codec == 1 else "ascii", self._errors)
        if len(b) >= 8192:
            while len(self._pending) > 0:
                self._writeflush()
        if len(b) > 0:
            self._pending.append(b)
            self._pending_count += len(b)
        if self._pending_count >= 8192 or needflush or self._write_through:
            self._writeflush()
        if needflush:
            self._buffer.flush()
        if self._snapshot:
            self._set_decoded("")
            self._snapshot = False
        if self._readable:
            self._reset_decoder()
        return n

    def writelines(self, lines, /) -> None:
        """Write a list of lines to stream.

        Line separators are not added, so it is usual for each of the
        lines provided to have a line separator at the end.
        """
        if self.closed:
            raise ValueError("I/O operation on closed file.")
        for line in lines:
            self.write(line)

    def read(self, size: int | None = -1, /) -> str:
        self._check_closed()
        if not self._readable:
            _unsupported("not readable")
        self._writeflush()
        n = -1 if size is None else size
        if n < 0:
            decoded = self._decode(_buffer_read(self._buffer), True)
            result = self._take(-1) + decoded
            if self._snapshot:
                self._set_decoded("")
                self._snapshot = False
            return result
        result = self._take(n)
        remaining = n - (len(result) if self._dascii else _nchars(result, 0, len(result)))
        while remaining > 0:
            if not self._read_chunk(remaining):
                break
            more = self._take(remaining)
            remaining -= len(more) if self._dascii else _nchars(more, 0, len(more))
            result = result + more
        return result

    def _line_end(self, line: str, start: int) -> int:
        # _PyIO_find_line_ending: the offset just past the first line ending of line[start:], or
        # -1 - the offset up to which there is none (a final \r of newline "\r\n" may begin one)
        if self._readtranslate:
            i = line.find("\n", start)
            return i + 1 if i >= 0 else -1 - len(line)
        if self._readuniversal:
            i = line.find("\n", start)
            j = line.find("\r", start, i if i >= 0 else len(line))
            if j >= 0:
                return j + 2 if j + 1 < len(line) and line[j + 1] == "\n" else j + 1
            return i + 1 if i >= 0 else -1 - len(line)
        i = line.find(self._readnl, start)
        if i >= 0:
            return i + len(self._readnl)
        if len(self._readnl) == 1:
            return -1 - len(line)
        j = line.find("\r", max(len(line) - 1, start))
        return -1 - (j if j >= 0 else len(line))

    def _readline(self, limit: int) -> str:
        # _textiowrapper_readline: the next line, or its first limit characters (limit >= 0)
        self._check_closed()
        self._writeflush()
        chunks: list[str] = []
        chunked = 0  # (the characters in chunks)
        remaining = ""  # what is left of a chunk, where a line ending may begin
        line = ""
        have = False
        start = 0
        endpos = 0
        offset = 0  # (the bytes of remaining that begin line)
        while True:
            more = True
            while self._decoded == "":
                more = self._read_chunk(0)
                if not more:
                    break
            if not more:
                self._set_decoded("")
                self._snapshot = False
                break
            if remaining == "":
                line = self._decoded
                start = self._used
                offset = 0
            else:
                line = remaining + self._decoded
                start = 0
                offset = len(remaining)
                remaining = ""
            have = True
            endpos = self._line_end(line, start)
            if endpos >= 0:
                if limit >= 0 and _nchars(line, start, endpos) + chunked >= limit:
                    endpos = _skip(line, start, limit - chunked)
                break
            endpos = -1 - endpos
            if limit >= 0 and _nchars(line, start, endpos) + chunked >= limit:
                endpos = _skip(line, start, limit - chunked)
                break
            if endpos > start:
                s = line[start:endpos]
                chunks.append(s)
                if limit >= 0:
                    chunked += _nchars(s, 0, len(s))
            if endpos < len(line):
                remaining = line[endpos:]
            have = False
            self._set_decoded("")
        if have:
            self._used = endpos - offset
            if start > 0 or endpos < len(line):
                line = line[start:endpos]
        else:
            line = ""
        if remaining != "":
            chunks.append(remaining)
        if len(chunks) > 0:
            if have:
                chunks.append(line)
            line = "".join(chunks)
        return line

    def readline(self, size: int = -1, /) -> str:
        return self._readline(size)

    def readlines(self, hint: int | None = -1, /) -> list[str]:
        """Return a list of lines from the stream.

        hint can be specified to control the number of lines read: no more
        lines will be read if the total size (in bytes/characters) of all
        lines so far exceeds hint.
        """
        lines: list[str] = []
        h = -1 if hint is None else hint
        length = 0
        for line in self:
            lines.append(line)
            if h > 0:
                n = len(line) if line.isascii() else _nchars(line, 0, len(line))
                if n > h - length:
                    break
                length += n
        return lines

    def __iter__(self) -> Self:
        """Implement iter(self)."""
        if self.closed:
            raise ValueError("I/O operation on closed file.")
        return self

    def __next__(self) -> str:
        """Implement next(self)."""
        self._telling = False
        line = self._readline(-1)
        if line == "":
            self._snapshot = False
            self._telling = self._seekable
            raise StopIteration
        return line

    def flush(self) -> None:
        self._check_closed()
        self._telling = self._seekable
        self._writeflush()
        self._buffer.flush()

    def close(self) -> None:
        if self.closed:
            return
        try:
            self.flush()
        except BaseException:
            # (the buffer is closed all the same; what close() raises has the flush's as context)
            self._buffer.close()
            raise
        self._buffer.close()

    def __enter__(self):  # (compiled only where a with statement calls it, as __exit__ is)
        if self.closed:
            raise ValueError("I/O operation on closed file.")
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def readable(self) -> bool:
        return self._buffer.readable()

    def writable(self) -> bool:
        return self._buffer.writable()

    def seekable(self) -> bool:
        return self._buffer.seekable()

    def isatty(self) -> bool:
        return self._buffer.isatty()

    def fileno(self) -> int:
        return self._buffer.fileno()
