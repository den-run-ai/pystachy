"""librt.internal as Pystachy compiles it: mypy's binary cache codec.

The API of librt 0.16.0's internal module, whose byte formats and checks follow its C source
(internal/librt_internal.c, Copyright (c) 2025 Mypyc contributors, MIT License; see
THIRD_PARTY_NOTICES), in the subset: a WriteBuffer keeps its bytes as chunks that getvalue()
joins, and a ReadBuffer reads its bytes at a position. Reads advance as the C code's do, also
past what they consumed before an error. Values are little-endian:

- bool: one byte, 0 or 1; tag: one byte (0 to 255); float: 8 bytes (IEEE 754 double).
- int: one byte (last bit 0, 7 bits: -10 to 117), two (last bits 01, 14 bits: -100 to
  16283), four (last bits 011, 29 bits: -10000 to 536860911), else 15, then the byte length
  times 2 plus the sign as a short int, then the absolute value's bytes.
- str, bytes: the length as a short int, then the bytes (UTF-8 for a str).

A long int's value must fit Pystachy's int: reading a larger one raises OverflowError, where
CPython's int holds it. write_tag() of an int outside 0 to 255 raises CPython's ValueError
for u8 (librt 0.16.0's extension crashes there).
"""
import struct

_MIN_ONE_BYTE_INT = -10
_MAX_ONE_BYTE_INT = 117
_MIN_TWO_BYTES_INT = -100
_MAX_TWO_BYTES_INT = 16283
_MIN_FOUR_BYTES_INT = -10000
_MAX_FOUR_BYTES_INT = 536860911
_TWO_BYTES_INT_BIT = 1
_FOUR_BYTES_INT_BIT = 2
_FOUR_BYTES_INT_TRAILER = 3
_LONG_INT_TRAILER = 15

# the tags of mypy's cache (mypy/cache.py, nodes.py and types.py), which extract_symbol skips
_LITERAL_FALSE = 0
_LITERAL_TRUE = 1
_LITERAL_NONE = 2
_LITERAL_INT = 3
_LITERAL_STR = 4
_LITERAL_BYTES = 5
_LITERAL_FLOAT = 6
_LITERAL_COMPLEX = 7
_LITERAL_SENTINEL = 8
_LIST_GEN = 20
_LIST_INT = 21
_LIST_STR = 22
_LIST_BYTES = 23
_TUPLE_GEN = 24
_DICT_STR_GEN = 30
_MYPY_FILE = 50
_INSTANCE = 80
_INSTANCE_SIMPLE = 81
_INSTANCE_GENERIC = 82
_INSTANCE_STR = 83
_INSTANCE_OBJECT = 87
_RESERVED = 254
_END_TAG = 255
# the one-byte chunks, made once: tags, bools and one-byte ints append these
_BYTE: list[bytes] = [bytes([b]) for b in range(256)]


class ReadBuffer:
    def __init__(self, source: bytes) -> None:
        self._data = source
        self._pos = 0


class WriteBuffer:
    def __init__(self) -> None:
        self._chunks: list[bytes] = []

    def getvalue(self) -> bytes:
        return b"".join(self._chunks)


def _check_read(data: ReadBuffer, need: int) -> None:
    if len(data._data) - data._pos < need:
        raise ValueError("reading past the buffer end")


def _byte(data: ReadBuffer) -> int:
    _check_read(data, 1)
    b = data._data[data._pos]
    data._pos += 1
    return b


def _read_short_int(data: ReadBuffer, first: int) -> int:
    if first & _TWO_BYTES_INT_BIT == 0:
        return (first >> 1) + _MIN_ONE_BYTE_INT
    if first & _FOUR_BYTES_INT_BIT == 0:
        _check_read(data, 1)
        second = data._data[data._pos]
        data._pos += 1
        return (second << 6) + (first >> 2) + _MIN_TWO_BYTES_INT
    _check_read(data, 3)
    p = data._pos
    second = data._data[p]
    two_more = data._data[p + 1] | (data._data[p + 2] << 8)
    data._pos = p + 3
    return (two_more << 13) + (second << 5) + (first >> 3) + _MIN_FOUR_BYTES_INT


def _write_short_int(data: WriteBuffer, value: int) -> None:
    # (value is in the four-byte range)
    if value >= _MIN_ONE_BYTE_INT and value <= _MAX_ONE_BYTE_INT:
        data._chunks.append(_BYTE[(value - _MIN_ONE_BYTE_INT) << 1])
    elif value >= _MIN_TWO_BYTES_INT and value <= _MAX_TWO_BYTES_INT:
        x = ((value - _MIN_TWO_BYTES_INT) << 2) | _TWO_BYTES_INT_BIT
        data._chunks.append(bytes([x & 255, x >> 8]))
    else:
        x = ((value - _MIN_FOUR_BYTES_INT) << 3) | _FOUR_BYTES_INT_TRAILER
        data._chunks.append(bytes([x & 255, (x >> 8) & 255, (x >> 16) & 255, x >> 24]))


def _read_size(data: ReadBuffer, what: str) -> int:
    first = _byte(data)
    if first == _LONG_INT_TRAILER:
        raise ValueError(f"invalid {what}")
    size = _read_short_int(data, first)
    if size < 0:
        raise ValueError(f"invalid {what}")
    return size


def write_bool(data: WriteBuffer, value: bool, /) -> None:
    data._chunks.append(_BYTE[1] if value else _BYTE[0])


def read_bool(data: ReadBuffer, /) -> bool:
    b = _byte(data)
    if b != 0 and b != 1:
        raise ValueError("invalid bool value")
    return b == 1


def write_str(data: WriteBuffer, value: str, /) -> None:
    chunk = value.encode()  # (UTF-8, as CPython's default: the runtime looks up no codec name)
    if len(chunk) > _MAX_FOUR_BYTES_INT:
        raise ValueError("str too long to serialize")
    _write_short_int(data, len(chunk))
    data._chunks.append(chunk)


def read_str(data: ReadBuffer, /) -> str:
    size = _read_size(data, "str size")
    _check_read(data, size)
    p = data._pos
    s = data._data[p : p + size].decode()
    data._pos = p + size
    return s


def write_bytes(data: WriteBuffer, value: bytes, /) -> None:
    if len(value) > _MAX_FOUR_BYTES_INT:
        raise ValueError("bytes too long to serialize")
    _write_short_int(data, len(value))
    data._chunks.append(value)


def read_bytes(data: ReadBuffer, /) -> bytes:
    size = _read_size(data, "bytes size")
    _check_read(data, size)
    p = data._pos
    data._pos = p + size
    return data._data[p : p + size]


def write_float(data: WriteBuffer, value: float, /) -> None:
    data._chunks.append(struct.pack("<d", value))


def read_float(data: ReadBuffer, /) -> float:
    _check_read(data, 8)
    p = data._pos
    value: float = struct.unpack("<d", data._data[p : p + 8])[0]
    data._pos = p + 8
    return value


def write_int(data: WriteBuffer, value: int, /) -> None:
    if value >= _MIN_FOUR_BYTES_INT and value <= _MAX_FOUR_BYTES_INT:
        _write_short_int(data, value)
        return
    # 15, then the size in bytes and the sign, then the absolute value's bytes, low first
    data._chunks.append(_BYTE[_LONG_INT_TRAILER])
    digits = hex(value)
    neg = digits.startswith("-")
    digits = digits[3:] if neg else digits[2:]
    n = len(digits)
    _write_short_int(data, (((n + 1) // 2) << 1) | (1 if neg else 0))
    out: list[int] = []
    i = n
    while i > 1:
        out.append(int(digits[i - 2 : i], 16))
        i -= 2
    if i == 1:
        out.append(int(digits[0], 16))
    data._chunks.append(bytes(out))


def read_int(data: ReadBuffer, /) -> int:
    first = _byte(data)
    if first != _LONG_INT_TRAILER:
        return _read_short_int(data, first)
    size_and_sign = _read_short_int(data, _byte(data))
    if size_and_sign < 0:
        raise ValueError("invalid int data")
    size = size_and_sign >> 1
    _check_read(data, size)
    p = data._pos
    value = 0
    # (accumulated with the sign: a negative value's magnitude may not fit, -2**63's)
    for i in range(size - 1, -1, -1):
        value = value * 256 - data._data[p + i] if size_and_sign & 1 else value * 256 + data._data[p + i]
    data._pos = p + size
    return value


def write_tag(data: WriteBuffer, value: int, /) -> None:
    if value < 0 or value >= 256:
        raise ValueError("int too large or small to convert to u8")
    data._chunks.append(_BYTE[value])


def read_tag(data: ReadBuffer, /) -> int:
    return _byte(data)


def cache_version() -> int:
    return 0


def _skip(data: ReadBuffer, size: int) -> None:
    _check_read(data, size)
    data._pos += size


def _skip_int(data: ReadBuffer) -> None:
    first = _byte(data)
    if first != _LONG_INT_TRAILER:
        if first & _TWO_BYTES_INT_BIT == 0:
            return
        _skip(data, 1 if first & _FOUR_BYTES_INT_BIT == 0 else 3)
        return
    size_and_sign = _read_short_int(data, _byte(data))
    if size_and_sign < 0:
        raise ValueError("invalid int data")
    _skip(data, size_and_sign >> 1)


def _skip_str_bytes(data: ReadBuffer) -> None:
    first = _byte(data)
    if first == _LONG_INT_TRAILER:
        raise ValueError("unsupported size")
    size = _read_short_int(data, first)
    if size < 0:
        raise ValueError("invalid size")
    _skip(data, size)


def _read_count(data: ReadBuffer) -> int:
    first = _byte(data)
    if first == _LONG_INT_TRAILER:
        raise ValueError("unsupported size")
    size = _read_short_int(data, first)
    if size < 0:
        raise ValueError("invalid size")
    return size


def _skip_class(data: ReadBuffer) -> None:
    # The fields of a cache class whose own tag the caller has read, up to its END_TAG, as
    # librt_internal.c's _skip_class and _skip_object read them, in the same order, but with a
    # stack of the objects open rather than recursion (cache objects nest, and corrupt data
    # can nest them deeper than the recursion limit): kinds holds 0 for a class (fields to its
    # END_TAG), 1 for a list or tuple of tagged values and 2 for a dict of str keys and tagged
    # values, counts the items left of each of those
    kinds: list[int] = [0]
    counts: list[int] = [0]
    while len(kinds) > 0:
        kind = kinds[-1]
        if kind == 0:
            tag = _byte(data)
            if tag == _END_TAG:
                kinds.pop()
                counts.pop()
                continue
        elif counts[-1] == 0:
            kinds.pop()
            counts.pop()
            continue
        else:
            counts[-1] -= 1
            if kind == 2:
                _skip_str_bytes(data)
            tag = _byte(data)
        if tag == _LITERAL_STR or tag == _LITERAL_BYTES:
            _skip_str_bytes(data)
        elif tag == _LITERAL_NONE or tag == _LITERAL_FALSE or tag == _LITERAL_TRUE:
            pass
        elif tag == _LIST_GEN or tag == _TUPLE_GEN:
            counts.append(_read_count(data))
            kinds.append(1)
        elif tag == _LITERAL_INT:
            _skip_int(data)
        elif tag == _INSTANCE:
            second = _byte(data)
            if second >= _INSTANCE_STR and second <= _INSTANCE_OBJECT:
                pass
            elif second == _INSTANCE_SIMPLE:
                _skip_str_bytes(data)
            elif second == _INSTANCE_GENERIC:
                kinds.append(0)
                counts.append(0)
            else:
                raise ValueError(f"Unexpected instance tag: {second}")
        elif tag > _MYPY_FILE and tag < _RESERVED:
            # (MypyFile itself is excluded: a module's symbols are only cross-references)
            kinds.append(0)
            counts.append(0)
        elif tag == _LIST_INT:
            for _ in range(_read_count(data)):
                _skip_int(data)
        elif tag == _LIST_STR or tag == _LIST_BYTES:
            for _ in range(_read_count(data)):
                _skip_str_bytes(data)
        elif tag == _DICT_STR_GEN:
            counts.append(_read_count(data))
            kinds.append(2)
        elif tag == _LITERAL_FLOAT:
            _skip(data, 8)
        elif tag == _LITERAL_COMPLEX:
            _skip(data, 16)
        elif tag == _LITERAL_SENTINEL:
            _skip_str_bytes(data)
            _skip_str_bytes(data)
        else:
            raise ValueError(f"Unsupported tag: {tag}")


def extract_symbol(data: ReadBuffer, /) -> bytes:
    start = data._pos
    _skip_class(data)
    return data._data[start : data._pos]
