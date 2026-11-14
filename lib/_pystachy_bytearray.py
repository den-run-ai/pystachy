"""The bytearray type of the builtins, as a class of the subset.

Pystachy's own module, after CPython 3.13's Objects/bytearrayobject.c. A module that reads the
builtin name imports the class from here (Loader.parse), and bytearray(source, ...) is _new, a
function of its arguments' types (Gen.call): the class's __init__ takes none, so that every
bytearray is an object of the one class. A slice of one, an assignment to a slice and a deletion
of a slice are the class's _getslice, _setslice and _delslice, which the compiler calls with the
bounds as they are written (None where one is left out). Programs do not import the module and
it runs no code.

A bytearray holds a buffer and a length. The buffer is a bytes that this module alone holds and
writes in place: its len() is the bytearray's capacity, and no other code sees it, so a bytes
that a program holds never changes. What the module hands out (bytes(b), b.decode(), a slice, a
method's result) is a copy, and what it takes (the bytes b.extend() appends) it copies in.

The __pys_ba_* calls are compiler primitives of this module (Gen.ba_prim), each with its bounds
checked: a new buffer of zeros, the byte at an index, a store there (a value that is no byte
raises ValueError), a move of bytes between buffers, which may be one buffer, whether two runs
of bytes are the same, and the first index of a byte or of a run of bytes within bounds.
"""
from typing import Iterator

_MAX = 9223372036854775807


class bytearray:
    __slots__ = ("_b", "_n")

    def __init__(self) -> None:
        self._b = b""  # the buffer: its first _n bytes are the bytearray's (an empty one has none to write)
        self._n = 0

    def __len__(self) -> int:
        return self._n

    def __repr__(self) -> str:
        return "bytearray(" + repr(_bytes(self, 0, self._n)) + ")"

    def __bytes__(self) -> bytes:
        return _bytes(self, 0, self._n)

    def __iter__(self) -> Iterator[int]:
        # (the bytes as they are when each is reached, as CPython's iterator indexes the object)
        i = 0
        while i < self._n:
            yield __pys_ba_get(self._b, i)
            i += 1

    def __reversed__(self) -> Iterator[int]:
        i = self._n - 1
        while i >= 0:
            if i < self._n:
                yield __pys_ba_get(self._b, i)
            i -= 1

    def __getitem__(self, i: int) -> int:
        n = self._n
        if i < 0:
            i += n
        if i < 0 or i >= n:
            raise IndexError("bytearray index out of range")
        return __pys_ba_get(self._b, i)

    def __setitem__(self, i: int, value: int) -> None:
        n = self._n
        if i < 0:
            i += n
        if i < 0 or i >= n:
            raise IndexError("bytearray index out of range")
        __pys_ba_put(self._b, i, value)

    def __delitem__(self, i: int) -> None:
        n = self._n
        if i < 0:
            i += n
        if i < 0 or i >= n:
            raise IndexError("bytearray index out of range")
        __pys_ba_copy(self._b, i, self._b, i + 1, n - i - 1)
        self._n = n - 1

    def _getslice(self, lo: int | None, hi: int | None, st: int | None) -> "bytearray":
        start, step, count = _span(self._n, lo, hi, st)
        r = bytearray()
        _reserve(r, count)
        if step == 1:
            __pys_ba_copy(r._b, 0, self._b, start, count)
        else:
            for k in range(count):
                __pys_ba_put(r._b, k, __pys_ba_get(self._b, start + k * step))
        r._n = count
        return r

    def _setslice(self, lo: int | None, hi: int | None, st: int | None, value) -> None:
        if isinstance(value, int) or isinstance(value, str):
            raise TypeError("can assign only bytes, buffers, or iterables of ints in range(0, 256)")
        src = _items(value)  # (a copy where value is this bytearray)
        m = len(src)
        start, step, count = _span(self._n, lo, hi, st)
        if step == 1:
            # the count bytes from start give way to src's
            n = self._n
            tail = n - start - count
            _reserve(self, start + m + tail)
            __pys_ba_copy(self._b, start + m, self._b, start + count, tail)
            __pys_ba_copy(self._b, start, src, 0, m)
            self._n = start + m + tail
            return
        if m != count:
            raise ValueError(f"attempt to assign bytes of size {m} to extended slice of size {count}")
        for k in range(count):
            __pys_ba_put(self._b, start + k * step, src[k])

    def _delslice(self, lo: int | None, hi: int | None, st: int | None) -> None:
        n = self._n
        start, step, count = _span(n, lo, hi, st)
        if count == 0:
            return
        if step < 0:
            start += (count - 1) * step
            step = -step
        if step == 1:
            __pys_ba_copy(self._b, start, self._b, start + count, n - start - count)
            self._n = n - count
            return
        # every step-th byte from start goes, count of them: the others close up
        at = start
        gone = 0
        skip = start
        for i in range(start, n):
            if i == skip and gone < count:
                gone += 1
                skip += step
            else:
                __pys_ba_put(self._b, at, __pys_ba_get(self._b, i))
                at += 1
        self._n = n - count

    def __eq__(self, other) -> bool:
        if isinstance(other, bytearray):
            return self._n == other._n and __pys_ba_same(self._b, 0, other._b, 0, self._n)
        if isinstance(other, bytes):
            return self._n == len(other) and __pys_ba_same(self._b, 0, other, 0, self._n)
        return False

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other) -> bool:
        return _bytes(self, 0, self._n) < _ordered(other, "<")

    def __le__(self, other) -> bool:
        return _bytes(self, 0, self._n) <= _ordered(other, "<=")

    def __gt__(self, other) -> bool:
        return _bytes(self, 0, self._n) > _ordered(other, ">")

    def __ge__(self, other) -> bool:
        return _bytes(self, 0, self._n) >= _ordered(other, ">=")

    def __contains__(self, item) -> bool:
        if isinstance(item, int):
            if item < 0 or item > 255:
                raise ValueError("byte must be in range(0, 256)")
            return __pys_ba_find_byte(self._b, item, 0, self._n) >= 0
        return __pys_ba_find(self._b, _like(item), 0, self._n) >= 0

    def __add__(self, other) -> "bytearray":
        tail = _concat(other)
        r = bytearray()
        _reserve(r, self._n + len(tail))
        __pys_ba_copy(r._b, 0, self._b, 0, self._n)
        __pys_ba_copy(r._b, self._n, tail, 0, len(tail))
        r._n = self._n + len(tail)
        return r

    def __iadd__(self, other) -> "bytearray":
        if isinstance(other, bytearray) and other is self and self._n > 0:
            # (CPython: its buffer is taken for the operand while it is resized)
            raise BufferError("Existing exports of data: object cannot be re-sized")
        _append(self, _concat(other))
        return self

    def __mul__(self, count: int) -> "bytearray":
        r = bytearray()
        _repeat(r, self, count)
        return r

    def __imul__(self, count: int) -> "bytearray":
        t = bytearray()
        _repeat(t, self, count)
        self._b = t._b
        self._n = t._n
        return self

    def append(self, item: int) -> None:
        n = self._n
        if n == len(self._b):
            _reserve(self, n + 1)
        __pys_ba_put(self._b, n, item)
        self._n = n + 1

    def extend(self, iterable_of_ints) -> None:
        # (as CPython: nothing is appended where an item is no byte)
        _append(self, _items(iterable_of_ints))

    def insert(self, index: int, item: int) -> None:
        if item < 0 or item > 255:
            raise ValueError("byte must be in range(0, 256)")
        n = self._n
        if index < 0:
            index += n
            if index < 0:
                index = 0
        if index > n:
            index = n
        _reserve(self, n + 1)
        __pys_ba_copy(self._b, index + 1, self._b, index, n - index)
        __pys_ba_put(self._b, index, item)
        self._n = n + 1

    def pop(self, index: int = -1) -> int:
        n = self._n
        if n == 0:
            raise IndexError("pop from empty bytearray")
        if index < 0:
            index += n
        if index < 0 or index >= n:
            raise IndexError("pop index out of range")
        r = __pys_ba_get(self._b, index)
        __pys_ba_copy(self._b, index, self._b, index + 1, n - index - 1)
        self._n = n - 1
        return r

    def remove(self, value: int) -> None:
        if value < 0 or value > 255:
            raise ValueError("byte must be in range(0, 256)")
        n = self._n
        i = __pys_ba_find_byte(self._b, value, 0, n)
        if i < 0:
            raise ValueError("value not found in bytearray")
        __pys_ba_copy(self._b, i, self._b, i + 1, n - i - 1)
        self._n = n - 1

    def reverse(self) -> None:
        i = 0
        j = self._n - 1
        while i < j:
            x = __pys_ba_get(self._b, i)
            __pys_ba_put(self._b, i, __pys_ba_get(self._b, j))
            __pys_ba_put(self._b, j, x)
            i += 1
            j -= 1

    def clear(self) -> None:
        self._b = b""
        self._n = 0

    def copy(self) -> "bytearray":
        return _from(_bytes(self, 0, self._n))

    def __copy__(self) -> "bytearray":
        return _from(_bytes(self, 0, self._n))

    def __deepcopy__(self, memo) -> "bytearray":
        return _from(_bytes(self, 0, self._n))

    def decode(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        return _bytes(self, 0, self._n).decode(encoding, errors)

    def hex(self) -> str:
        return _bytes(self, 0, self._n).hex()

    def find(self, sub, start: int = 0, end: int = _MAX) -> int:
        lo, hi = _bounds(self._n, start, end)
        return _find(self, sub, lo, hi)

    def index(self, sub, start: int = 0, end: int = _MAX) -> int:
        lo, hi = _bounds(self._n, start, end)
        i = _find(self, sub, lo, hi)
        if i < 0:
            raise ValueError("subsection not found")
        return i

    def rfind(self, sub, start: int = 0, end: int = _MAX) -> int:
        return _bytes(self, 0, self._n).rfind(_sub(sub), start, end)

    def rindex(self, sub, start: int = 0, end: int = _MAX) -> int:
        return _bytes(self, 0, self._n).rindex(_sub(sub), start, end)

    def count(self, sub, start: int = 0, end: int = _MAX) -> int:
        return _bytes(self, 0, self._n).count(_sub(sub), start, end)

    def startswith(self, prefix, start: int = 0, end: int = _MAX) -> bool:
        if isinstance(prefix, tuple):
            return _bytes(self, 0, self._n).startswith(prefix, start, end)
        p = _like(prefix)
        lo, hi = _bounds(self._n, start, end)
        return hi - lo >= len(p) and __pys_ba_same(self._b, lo, p, 0, len(p))

    def endswith(self, suffix, start: int = 0, end: int = _MAX) -> bool:
        if isinstance(suffix, tuple):
            return _bytes(self, 0, self._n).endswith(suffix, start, end)
        p = _like(suffix)
        lo, hi = _bounds(self._n, start, end)
        return hi - lo >= len(p) and __pys_ba_same(self._b, hi - len(p), p, 0, len(p))

    def join(self, iterable_of_bytes) -> "bytearray":
        parts: list[bytes] = []
        for x in iterable_of_bytes:
            parts.append(_like(x))
        return _from(_bytes(self, 0, self._n).join(parts))

    def split(self, sep=None, maxsplit: int = -1) -> list["bytearray"]:
        if sep is None:
            return [_from(x) for x in _bytes(self, 0, self._n).split(None, maxsplit)]
        return [_from(x) for x in _bytes(self, 0, self._n).split(_like(sep), maxsplit)]

    def rsplit(self, sep=None, maxsplit: int = -1) -> list["bytearray"]:
        if sep is None:
            return [_from(x) for x in _bytes(self, 0, self._n).rsplit(None, maxsplit)]
        return [_from(x) for x in _bytes(self, 0, self._n).rsplit(_like(sep), maxsplit)]

    def splitlines(self, keepends: bool = False) -> list["bytearray"]:
        return [_from(x) for x in _bytes(self, 0, self._n).splitlines(keepends)]

    def partition(self, sep) -> tuple["bytearray", "bytearray", "bytearray"]:
        a, b, c = _bytes(self, 0, self._n).partition(_like(sep))
        return (_from(a), _from(b), _from(c))

    def rpartition(self, sep) -> tuple["bytearray", "bytearray", "bytearray"]:
        a, b, c = _bytes(self, 0, self._n).rpartition(_like(sep))
        return (_from(a), _from(b), _from(c))

    def replace(self, old, new, count: int = -1) -> "bytearray":
        return _from(_bytes(self, 0, self._n).replace(_like(old), _like(new), count))

    def strip(self, chars=None) -> "bytearray":
        if chars is None:
            return _from(_bytes(self, 0, self._n).strip())
        return _from(_bytes(self, 0, self._n).strip(_like(chars)))

    def lstrip(self, chars=None) -> "bytearray":
        if chars is None:
            return _from(_bytes(self, 0, self._n).lstrip())
        return _from(_bytes(self, 0, self._n).lstrip(_like(chars)))

    def rstrip(self, chars=None) -> "bytearray":
        if chars is None:
            return _from(_bytes(self, 0, self._n).rstrip())
        return _from(_bytes(self, 0, self._n).rstrip(_like(chars)))

    def removeprefix(self, prefix) -> "bytearray":
        return _from(_bytes(self, 0, self._n).removeprefix(_like(prefix)))

    def removesuffix(self, suffix) -> "bytearray":
        return _from(_bytes(self, 0, self._n).removesuffix(_like(suffix)))

    def translate(self, table: bytes | None, delete: bytes = b"") -> "bytearray":
        return _from(_bytes(self, 0, self._n).translate(table, delete))

    def upper(self) -> "bytearray":
        return _from(_bytes(self, 0, self._n).upper())

    def lower(self) -> "bytearray":
        return _from(_bytes(self, 0, self._n).lower())

    def capitalize(self) -> "bytearray":
        return _from(_bytes(self, 0, self._n).capitalize())

    def swapcase(self) -> "bytearray":
        return _from(_bytes(self, 0, self._n).swapcase())

    def center(self, width: int, fillbyte: bytes = b" ") -> "bytearray":
        return _from(_bytes(self, 0, self._n).center(width, fillbyte))

    def ljust(self, width: int, fillbyte: bytes = b" ") -> "bytearray":
        return _from(_bytes(self, 0, self._n).ljust(width, fillbyte))

    def rjust(self, width: int, fillbyte: bytes = b" ") -> "bytearray":
        return _from(_bytes(self, 0, self._n).rjust(width, fillbyte))

    def zfill(self, width: int) -> "bytearray":
        return _from(_bytes(self, 0, self._n).zfill(width))

    def isalnum(self) -> bool:
        return _bytes(self, 0, self._n).isalnum()

    def isalpha(self) -> bool:
        return _bytes(self, 0, self._n).isalpha()

    def isascii(self) -> bool:
        return _bytes(self, 0, self._n).isascii()

    def isdigit(self) -> bool:
        return _bytes(self, 0, self._n).isdigit()

    def islower(self) -> bool:
        return _bytes(self, 0, self._n).islower()

    def isspace(self) -> bool:
        return _bytes(self, 0, self._n).isspace()

    def isupper(self) -> bool:
        return _bytes(self, 0, self._n).isupper()

    @classmethod
    def fromhex(cls, string: str) -> "bytearray":
        return _from(bytes.fromhex(string))

    @staticmethod
    def maketrans(frm: bytes, to: bytes) -> bytes:
        return bytes.maketrans(frm, to)


def _reserve(b: bytearray, need: int) -> None:
    # room for need bytes: a larger buffer, by half again at least, with the bytes moved to it
    cap = len(b._b)
    if need <= cap:
        return
    grown = cap + (cap >> 1) + 16
    buf = __pys_ba_new(need if need > grown else grown)
    __pys_ba_copy(buf, 0, b._b, 0, b._n)
    b._b = buf


def _bytes(b: bytearray, lo: int, n: int) -> bytes:
    # a new bytes of the n bytes from lo
    r = __pys_ba_new(n)
    __pys_ba_copy(r, 0, b._b, lo, n)
    return r


def _from(data: bytes) -> bytearray:
    # a new bytearray of data's bytes
    r = bytearray()
    _append(r, data)
    return r


def _append(b: bytearray, data: bytes) -> None:
    n = b._n
    m = len(data)
    _reserve(b, n + m)
    __pys_ba_copy(b._b, n, data, 0, m)
    b._n = n + m


def _repeat(r: bytearray, b: bytearray, count: int) -> None:
    # r, which is empty, becomes count times b's bytes
    n = b._n
    if count <= 0 or n == 0:
        return
    if n > _MAX // count:
        raise MemoryError()
    _reserve(r, n * count)
    for k in range(count):
        __pys_ba_copy(r._b, k * n, b._b, 0, n)
    r._n = n * count


def _like(x) -> bytes:
    # the bytes of a bytes-like argument: a bytes itself, a bytearray's as they are now
    if isinstance(x, bytes):
        return x
    if isinstance(x, bytearray):
        return _bytes(x, 0, x._n)
    raise TypeError(f"a bytes-like object is required, not '{type(x).__name__}'")


def _arg(x):
    # an argument that bytes' own method takes: a bytearray's bytes, anything else as it is
    if isinstance(x, bytearray):
        return _bytes(x, 0, x._n)
    return x


def _sub(x) -> bytes:
    # what a search looks for: a bytes-like object's bytes, or the one byte an int is
    if isinstance(x, int):
        if x < 0 or x > 255:
            raise ValueError("byte must be in range(0, 256)")
        return bytes([x])
    return _like(x)


def _concat(x) -> bytes:
    # the operand of + and +=
    if isinstance(x, bytes):
        return x
    if isinstance(x, bytearray):
        return _bytes(x, 0, x._n)
    raise TypeError(f"can't concat {type(x).__name__} to bytearray")


def _ordered(x, op: str) -> bytes:
    # the operand of an ordering comparison
    if isinstance(x, bytes):
        return x
    if isinstance(x, bytearray):
        return _bytes(x, 0, x._n)
    raise TypeError(f"'{op}' not supported between instances of 'bytearray' and '{type(x).__name__}'")


def _items(source) -> bytes:
    # the bytes that an iterable of ints, a bytes or a bytearray gives, each checked to be a byte
    if isinstance(source, bytes):
        return source
    if isinstance(source, bytearray):
        return _bytes(source, 0, source._n)
    t = bytearray()
    for x in source:
        t.append(x)
    return _bytes(t, 0, t._n)


def _bounds(n: int, start: int, end: int) -> tuple[int, int]:
    # the bounds of a search, as a slice's are: within 0 and n
    if start < 0:
        start += n
        if start < 0:
            start = 0
    if end < 0:
        end += n
        if end < 0:
            end = 0
    if end > n:
        end = n
    return (start, end)


def _find(b: bytearray, sub, lo: int, hi: int) -> int:
    if isinstance(sub, int):
        if sub < 0 or sub > 255:
            raise ValueError("byte must be in range(0, 256)")
        return __pys_ba_find_byte(b._b, sub, lo, hi) if lo <= hi else -1
    p = _like(sub)
    if lo > hi or hi - lo < len(p):
        return -1
    return __pys_ba_find(b._b, p, lo, hi)


def _span(n: int, lo: int | None, hi: int | None, st: int | None) -> tuple[int, int, int]:
    # the first index, the step and the count of the items of a slice lo:hi:st of n items
    # (CPython's PySlice_AdjustIndices)
    step = 1 if st is None else st
    if step == 0:
        raise ValueError("slice step cannot be zero")
    if step < -_MAX:
        step = -_MAX
    if step > 0:
        start = 0 if lo is None else lo
        stop = n if hi is None else hi
        if start < 0:
            start += n
            if start < 0:
                start = 0
        elif start > n:
            start = n
        if stop < 0:
            stop += n
            if stop < 0:
                stop = 0
        elif stop > n:
            stop = n
        return (start, step, (stop - start - 1) // step + 1 if stop > start else 0)
    start = n - 1 if lo is None else lo
    stop = -1 if hi is None else hi
    if lo is not None:
        if start < 0:
            start += n
            if start < 0:
                start = -1
        elif start >= n:
            start = n - 1
    if hi is not None:
        if stop < 0:
            stop += n
            if stop < 0:
                stop = -1
        elif stop >= n:
            stop = n - 1
    return (start, step, (start - stop - 1) // (-step) + 1 if stop < start else 0)


def _new(source, encoding=None, errors=None) -> bytearray:
    # bytearray(source[, encoding[, errors]])
    r = bytearray()
    if isinstance(source, str):
        if encoding is None:
            raise TypeError("string argument without an encoding" if errors is None else "string argument without an encoding")
        _append(r, source.encode(encoding) if errors is None else source.encode(encoding, errors))
        return r
    if encoding is not None:
        raise TypeError("encoding without a string argument")
    if errors is not None:
        raise TypeError("errors without a string argument")
    if source is None:
        raise TypeError("cannot convert 'NoneType' object to bytearray")
    if isinstance(source, int):
        if source < 0:
            raise ValueError("negative count")
        _reserve(r, source)
        r._n = source
        return r
    _append(r, _items(source))
    return r
