"""Binary files: the objects CPython's open() returns for a mode with "b", written for Pystachy.

CPython 3.13.16's open() (Modules/_io/_iomodule.c) makes a FileIO (Modules/_io/fileio.c) and, unless
buffering=0, a BufferedReader, BufferedWriter or BufferedRandom over it (Modules/_io/bufferedio.c).
Here each is an object over the runtime's file of that mode (runtime.c's pys_bopen), whose bytes are
read and written as they are; a buffered file's writes reach the OS when CPython's do, and its reads
and writes are at its position. The methods check what CPython's check, in its order, and raise its
errors. The compiler makes open(file, mode) of a literal binary mode a call of open_reader(),
open_writer(), open_random() or open_raw() (loader.py's binary_opens); type() and repr() name these
classes as _io's. The __pys_bfile_* calls are compiler primitives, private to this module.
"""

from typing import Self, TextIO


def _closed(message: str) -> None:
    raise ValueError(message)


class BinaryIO:
    # the runtime's file (_raw) of a binary mode, as CPython's class _kind of open(): BufferedReader
    # 1, BufferedWriter 2, BufferedRandom 3, FileIO 4 (which raises FileIO's errors). Each derives
    # from this class, which is the type of what open() makes: a name may hold a file of each mode
    _raw: TextIO
    _kind: int

    def __init__(self, raw: TextIO, kind: int) -> None:
        self._raw = raw
        self._kind = kind

    @property
    def closed(self) -> bool:
        return self._raw.closed

    @property
    def name(self) -> str:
        return self._raw.name

    @property
    def mode(self) -> str:
        return self._raw.mode

    def _readable(self) -> bool:
        return self._kind != 2 and (self._kind != 4 or self._raw.mode.startswith("r") or self._raw.mode.endswith("+"))

    def _writable(self) -> bool:
        return self._kind != 1 and (self._kind != 4 or not self._raw.mode.startswith("r") or self._raw.mode.endswith("+"))

    def _check_raw(self) -> None:
        # (FileIO's methods, and a buffered file's that its FileIO answers)
        if self._raw.closed:
            _closed("I/O operation on closed file")

    def _check_read(self, size: int, what: str) -> None:
        if self._kind == 4:
            self._check_raw()
            if not self._readable():
                __pys_bfile_unsupported("File not open for reading")
        else:
            if not self._readable():
                __pys_bfile_unsupported(what)
            if size < -1 and what == "read":
                raise ValueError("read length must be non-negative or -1")
            if self._raw.closed:
                _closed(what + " of closed file")

    def _check_write(self) -> None:
        if self._kind == 4:
            self._check_raw()
            if not self._writable():
                __pys_bfile_unsupported("File not open for writing")
        else:
            if not self._writable():
                __pys_bfile_unsupported("write")
            if self._raw.closed:
                _closed("write to closed file")

    def read(self, size: int | None = -1, /) -> bytes:
        n = -1 if size is None else size
        self._check_read(n, "read")
        return __pys_bfile_read(self._raw, n if n >= 0 else -1)

    def readline(self, size: int | None = -1, /) -> bytes:
        n = -1 if size is None else size
        if self._kind == 2:
            __pys_bfile_unsupported("read")
        if self._kind == 4:
            self._check_raw()
            if not self._readable():
                __pys_bfile_unsupported("File not open for reading")
        elif self._raw.closed:
            _closed("readline of closed file")
        return __pys_bfile_readline(self._raw, n if n >= 0 else -1)

    def readlines(self, hint: int | None = -1, /) -> list[bytes]:
        if self._raw.closed:
            _closed("I/O operation on closed file.")
        n = -1 if hint is None else hint
        lines: list[bytes] = []
        total = 0
        while True:
            line = self.readline()
            if len(line) == 0:
                break
            lines.append(line)
            total += len(line)
            if 0 < n <= total:
                break
        return lines

    def write(self, b: bytes, /) -> int:
        self._check_write()
        return __pys_bfile_write(self._raw, b)

    def writelines(self, lines: list[bytes], /) -> None:
        if self._raw.closed:
            _closed("I/O operation on closed file.")
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        if self._raw.closed:
            _closed("flush of closed file" if self._kind == 2 or self._kind == 3 else "I/O operation on closed file.")
        self._raw.flush()

    def close(self) -> None:
        self._raw.close()

    def fileno(self) -> int:
        return self._raw.fileno()

    def isatty(self) -> bool:
        self._check_raw()
        return __pys_bfile_isatty(self._raw)

    def readable(self) -> bool:
        if self._kind == 2:
            return False
        self._check_raw()
        return self._readable()

    def writable(self) -> bool:
        if self._kind == 1:
            return False
        self._check_raw()
        return self._writable()

    def seekable(self) -> bool:
        self._check_raw()
        return __pys_bfile_seekable(self._raw)

    def seek(self, pos: int, whence: int = 0, /) -> int:
        if self._kind != 4:
            if whence < 0 or whence > 4:
                raise ValueError(f"whence value {whence} unsupported")
            if self._raw.closed:
                _closed("seek of closed file")
        else:
            self._check_raw()
        return __pys_bfile_seek(self._raw, pos, whence)

    def tell(self) -> int:
        self._check_raw()
        return __pys_bfile_tell(self._raw)

    def truncate(self, pos: int | None = None, /) -> int:
        if self._kind == 4:
            self._check_raw()
            if not self._writable():
                __pys_bfile_unsupported("File not open for writing")
        else:
            if self._raw.closed:
                _closed("truncate of closed file")
            if not self._writable():
                __pys_bfile_unsupported("truncate")
        return __pys_bfile_truncate(self._raw, __pys_bfile_tell(self._raw) if pos is None else pos)

    def readall(self) -> bytes:
        if self._kind != 4:
            raise AttributeError(f"'_io.{type(self).__name__}' object has no attribute 'readall'")
        self._check_read(-1, "read")
        return __pys_bfile_read(self._raw, -1)

    def __iter__(self) -> Self:
        if self._raw.closed:
            _closed("I/O operation on closed file.")
        return self

    def __next__(self) -> bytes:
        line = self.readline()
        if len(line) == 0:
            raise StopIteration
        return line

    def __enter__(self):  # (compiled only where a with statement calls it, as __exit__ is)
        if self._raw.closed:
            _closed("I/O operation on closed file.")
        return self

    def __exit__(self, *args) -> None:
        self.close()


class BufferedReader(BinaryIO):
    def __repr__(self) -> str:
        return f"<_io.BufferedReader name={self._raw.name!r}>"


class BufferedWriter(BinaryIO):
    def __repr__(self) -> str:
        return f"<_io.BufferedWriter name={self._raw.name!r}>"


class BufferedRandom(BinaryIO):
    def __repr__(self) -> str:
        return f"<_io.BufferedRandom name={self._raw.name!r}>"


class FileIO(BinaryIO):
    def __repr__(self) -> str:
        if self._raw.closed:
            return "<_io.FileIO [closed]>"
        return f"<_io.FileIO name={self._raw.name!r} mode={self._raw.mode!r} closefd=True>"


# open(file, mode, buffering, encoding, errors, newline) of a literal binary mode, which the compiler
# makes a call of one of these, by the class CPython's open() makes for that mode (buffering=0: open_raw)
def open_reader(file: str, mode: str = "rb", buffering: int = -1, encoding: str | None = None, errors: str | None = None,
                newline: str | None = None) -> BinaryIO:
    return BufferedReader(__pys_bfile_open(file, mode, encoding, errors, newline, buffering), 1)


def open_writer(file: str, mode: str = "wb", buffering: int = -1, encoding: str | None = None, errors: str | None = None,
                newline: str | None = None) -> BinaryIO:
    return BufferedWriter(__pys_bfile_open(file, mode, encoding, errors, newline, buffering), 2)


def open_random(file: str, mode: str = "r+b", buffering: int = -1, encoding: str | None = None, errors: str | None = None,
                newline: str | None = None) -> BinaryIO:
    return BufferedRandom(__pys_bfile_open(file, mode, encoding, errors, newline, buffering), 3)


def open_raw(file: str, mode: str = "rb", buffering: int = 0, encoding: str | None = None, errors: str | None = None,
             newline: str | None = None) -> BinaryIO:
    return FileIO(__pys_bfile_open(file, mode, encoding, errors, newline, buffering), 4)
