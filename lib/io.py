"""The io module's in-memory text stream, StringIO, written for Pystachy.

CPython's io is a C module (Modules/_io); this one has StringIO, after Modules/_io/stringio.c of
CPython 3.13.16: the same reads, writes, seeks, newline translation and errors, on a str buffer
(lib/README.md). Positions and sizes count a str's bytes past ASCII, as len() and slicing do.
"""

from typing import Iterator

__all__ = ["StringIO", "SEEK_SET", "SEEK_CUR", "SEEK_END"]

SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2


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

    def __iter__(self) -> Iterator[str]:
        # the lines from the position on, read when the loop starts (an iterator class, which
        # would read each line as the loop asks for it, is not supported)
        self._check_base()
        return iter(self.readlines())

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
