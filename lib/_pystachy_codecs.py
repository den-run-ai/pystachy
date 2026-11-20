# Pystachy's _codecs: CPython 3.13's C module of codec functions (Modules/_codecsmodule.c), which
# CPython builds into its interpreter and imports instead of this file. Pystachy loads it for import
# _codecs, which lib/codecs.py does. Its codecs are UTF-8, Latin-1 and ASCII, as str.encode() and
# bytes.decode() have them, and the charmap codec of the table codecs (encodings.cp1252 ...), with
# CPython's errors and messages. The UTF-16, UTF-32, UTF-7 and escape codecs and the codec
# registry (lookup()) raise NotImplementedError, and so do the error handler functions but
# strict_errors(): Pystachy's UnicodeError has no start, end and object attributes for them.
from typing import Callable

# the C module's names, which from _codecs import * binds (codecs.py's own error handler names are
# not among them)
__all__ = ["ascii_decode", "ascii_encode", "charmap_build", "charmap_decode", "charmap_encode",
           "decode", "encode", "escape_decode", "escape_encode", "latin_1_decode",
           "latin_1_encode", "lookup", "lookup_error", "raw_unicode_escape_decode",
           "raw_unicode_escape_encode", "readbuffer_encode", "register", "register_error",
           "unicode_escape_decode", "unicode_escape_encode", "unregister", "utf_16_be_decode",
           "utf_16_be_encode", "utf_16_decode", "utf_16_encode", "utf_16_ex_decode",
           "utf_16_le_decode", "utf_16_le_encode", "utf_32_be_decode", "utf_32_be_encode",
           "utf_32_decode", "utf_32_encode", "utf_32_ex_decode", "utf_32_le_decode",
           "utf_32_le_encode", "utf_7_decode", "utf_7_encode", "utf_8_decode", "utf_8_encode"]

# the error handlers register_error() registered, by name
_handlers: dict[str, Callable[[UnicodeError], tuple[str, int]]] = {}
_BUILTIN_HANDLERS = ["strict", "ignore", "replace", "xmlcharrefreplace", "backslashreplace", "namereplace",
                     "surrogateescape", "surrogatepass"]


def _errors(errors: str | None) -> str:
    # a codec function's errors, of which None is "strict"
    return "strict" if errors is None else errors


def _seq(b: bytes, i: int, n: int) -> int:
    # the length of the UTF-8 sequence at b[i], which is a character's; 1 for a byte that begins
    # none, which is the character of that code point (a byte that chr() makes in Pystachy), as
    # Pystachy's str methods read a str's bytes: an overlong sequence's first byte and one past
    # U+10FFFF's begin none (#1587)
    c = b[i]
    if c < 0xC2 or c > 0xF4:
        return 1
    k = 2 if c < 0xE0 else 3 if c < 0xF0 else 4
    if i + k > n:
        return 1
    for j in range(i + 1, i + k):
        if b[j] & 0xC0 != 0x80:
            return 1
    if (c == 0xE0 and b[i + 1] < 0xA0) or (c == 0xF0 and b[i + 1] < 0x90) or (c == 0xF4 and b[i + 1] >= 0x90):
        return 1
    return k


def _chars(s: str) -> int:
    # the number of characters of s, which a codec function consumes (len() counts the bytes of a
    # str in Pystachy)
    b = s.encode("utf-8", "surrogatepass")
    n = len(b)
    count = 0
    i = 0
    while i < n:
        i += _seq(b, i, n)
        count += 1
    return count


def _codepoints(s: str) -> list[int]:
    # the code points of s's characters
    b = s.encode("utf-8", "surrogatepass")
    out: list[int] = []
    i = 0
    n = len(b)
    while i < n:
        k = _seq(b, i, n)
        c = b[i]
        v = c if k == 1 else c & (0x1F if k == 2 else 0x0F if k == 3 else 0x07)
        for j in range(i + 1, i + k):
            v = (v << 6) | (b[j] & 0x3F)
        out.append(v)
        i += k
    return out


def _utf8_tail(data: bytes) -> int:
    # the number of bytes at data's end that begin a UTF-8 sequence without ending it: a decode
    # that is not final leaves them for more data, as CPython's (Objects/stringlib/codecs.h)
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


def utf_8_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    return (s.encode("utf-8", _errors(errors)), _chars(s))


def utf_8_decode(data: bytes, errors: str | None = None, final: bool = False, /) -> tuple[str, int]:
    k = len(data) if final else len(data) - _utf8_tail(data)
    if k == len(data):
        return (data.decode("utf-8", _errors(errors)), k)
    # the bytes before the tail, where a sequence they end without completing is one that the
    # tail's first byte interrupts (an invalid continuation byte): a NUL interrupts it as that byte
    # does, and is one more character, dropped
    return ((data[:k] + b"\x00").decode("utf-8", _errors(errors))[:-1], k)


def latin_1_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    return (s.encode("latin-1", _errors(errors)), _chars(s))


def latin_1_decode(data: bytes, errors: str | None = None, /) -> tuple[str, int]:
    return (data.decode("latin-1", _errors(errors)), len(data))


def ascii_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    return (s.encode("ascii", _errors(errors)), _chars(s))


def ascii_decode(data: bytes, errors: str | None = None, /) -> tuple[str, int]:
    return (data.decode("ascii", _errors(errors)), len(data))


def readbuffer_encode(data: bytes, errors: str | None = None, /) -> tuple[bytes, int]:
    return (data, len(data))


def charmap_build(map: str, /) -> dict[int, int]:
    # the encoding map of decoding table map: each character's code point to its byte (index), of
    # the table's first 256 characters, where CPython's is an EncodingMap object, a trie that
    # leaves U+FFFE (undefined) out, if the table maps byte 0 to U+0000 and has no other U+0000
    # and no character beyond the BMP, and if the trie fits; else a dict of every character
    # (PyUnicode_BuildEncodingMap() in Objects/unicodeobject.c)
    cps = _codepoints(map)[:256]
    if len(cps) == 0:
        raise TypeError("bad argument type for built-in operation")
    trie = cps[0] == 0
    level1: set[int] = set()
    level2: set[int] = set()
    for c in cps[1:]:
        if c == 0 or c > 0xFFFF:
            trie = False
        elif c != 0xFFFE:
            level1.add(c >> 11)
            level2.add(c >> 7)
    if len(level1) >= 0xFF or len(level2) >= 0xFF:
        trie = False
    out: dict[int, int] = {}
    for i in range(len(cps)):
        if not trie or cps[i] != 0xFFFE:
            out[cps[i]] = i
    return out


def _backslash(cp: int) -> str:
    return "\\x%02x" % cp if cp < 0x100 else "\\u%04x" % cp if cp < 0x10000 else "\\U%08x" % cp


def charmap_encode(s: str, errors: str | None = None, mapping: dict[int, int] | None = None, /) -> tuple[bytes, int]:
    if mapping is None:
        return latin_1_encode(s, errors)
    e = _errors(errors)
    cps = _codepoints(s)
    out: list[int] = []
    n = len(cps)
    i = 0
    while i < n:
        if cps[i] in mapping:
            out.append(mapping[cps[i]])
            i += 1
            continue
        # the run of characters from i that the map has not, which the error handler gets, and
        # the characters of its replacement, which the map encodes too (charmap_encoding_error()
        # in Objects/unicodeobject.c)
        j = i + 1
        while j < n and cps[j] not in mapping:
            j += 1
        rep: list[int] = []
        if e == "replace":
            rep = [63] * (j - i)
        elif e == "xmlcharrefreplace":
            for c in cps[i:j]:
                rep.extend(_codepoints("&#" + str(c) + ";"))
        elif e == "backslashreplace":
            for c in cps[i:j]:
                rep.extend(_codepoints(_backslash(c)))
        elif e == "surrogateescape" and all(0xDC80 <= c <= 0xDCFF for c in cps[i:j]):
            for c in cps[i:j]:
                out.append(c - 0xDC00)  # (the bytes the surrogates stand for, as they are)
            i = j
            continue
        elif e != "ignore" and e != "strict" and e != "surrogateescape" and e != "surrogatepass":
            if e in _handlers:
                raise NotImplementedError("a handler of codecs.register_error() is not supported: Pystachy's UnicodeError has no start, end and object attributes")
            raise LookupError("unknown error handler name '" + e + "'")
        elif e != "ignore":
            raise UnicodeEncodeError("charmap", s, i, j, "character maps to <undefined>")
        for c in rep:
            if c not in mapping:
                raise UnicodeEncodeError("charmap", s, i, j, "character maps to <undefined>")
            out.append(mapping[c])
        i = j
    return (bytes(out), n)


_tables: dict[str, list[int]] = {}


def charmap_decode(data: bytes, errors: str | None = None, mapping: str | None = None, /) -> tuple[str, int]:
    if mapping is None:
        return latin_1_decode(data, errors)
    e = _errors(errors)
    if mapping not in _tables:
        _tables[mapping] = _codepoints(mapping)
    table = _tables[mapping]
    out: list[str] = []
    for i in range(len(data)):
        b = data[i]
        cp = table[b] if b < len(table) else 0xFFFE
        if cp != 0xFFFE:
            out.append("%c" % cp)  # (the character's UTF-8, where chr() of 128 to 255 is a byte)
        elif e == "replace":
            out.append("�")
        elif e == "ignore":
            pass
        elif e == "backslashreplace":
            out.append("\\x%02x" % b)
        elif e == "surrogateescape" and b >= 128:
            out.append("%c" % (0xDC00 + b))
        elif e == "xmlcharrefreplace" or e == "namereplace":
            raise TypeError("don't know how to handle UnicodeDecodeError in error callback")
        elif e != "strict" and e != "surrogateescape" and e != "surrogatepass":
            if e in _handlers:
                raise NotImplementedError("a handler of codecs.register_error() is not supported: Pystachy's UnicodeError has no start, end and object attributes")
            raise LookupError("unknown error handler name '" + e + "'")
        else:
            raise UnicodeDecodeError("charmap", data, i, i + 1, "character maps to <undefined>")
    return ("".join(out), len(data))


def _typename(obj) -> str:
    # type(obj).__name__, which Pystachy has of exceptions only, of the types a codec takes
    if isinstance(obj, bytes):
        return "bytes"
    elif isinstance(obj, str):
        return "str"
    elif isinstance(obj, bool):
        return "bool"
    elif isinstance(obj, int):
        return "int"
    elif isinstance(obj, float):
        return "float"
    else:
        return type(obj).__name__


def _codec(encoding: str) -> str:
    # the codec encoding names, of the three (LookupError for another), told by how it encodes é
    b = "\xe9".encode(encoding, "replace")
    return "utf_8" if b == b"\xc3\xa9" else "latin_1" if b == b"\xe9" else "ascii"


def encode(obj, encoding: str = "utf-8", errors: str = "strict"):
    """Encodes obj using the codec registered for encoding.

The default encoding is 'utf-8'.  errors may be given to set a
different error handling scheme.  Default is 'strict' meaning that
encoding errors raise a ValueError.  Other possible values are 'ignore',
'replace' and 'backslashreplace' as well as any other name registered
with codecs.register_error that can handle ValueErrors."""
    k = _codec(encoding)
    if not isinstance(obj, str):
        raise TypeError(k + "_encode() argument 1 must be str, not " + _typename(obj))
    return obj.encode(encoding, errors)


def decode(obj, encoding: str = "utf-8", errors: str = "strict"):
    """Decodes obj using the codec registered for encoding.

Default encoding is 'utf-8'.  errors may be given to set a
different error handling scheme.  Default is 'strict' meaning that
encoding errors raise a ValueError.  Other possible values are 'ignore',
'replace' and 'backslashreplace' as well as any other name registered
with codecs.register_error that can handle ValueErrors."""
    _codec(encoding)
    if not isinstance(obj, bytes):
        raise TypeError("a bytes-like object is required, not '" + _typename(obj) + "'")
    return obj.decode(encoding, errors)


def register(search_function, /) -> None:
    """Register a codec search function.

Search functions are expected to take one argument, the encoding
name in all lower case letters, and either return None, or a tuple
of functions (encoder, decoder, stream_reader, stream_writer) (or
a CodecInfo object)."""
    # (Pystachy has no codec registry: lookup() raises NotImplementedError)


def unregister(search_function, /) -> None:
    """Unregister a codec search function and clear the registry's cache.

If the search function is not registered, do nothing."""


def lookup(encoding, /):
    """Looks up a codec tuple in the Python codec registry and returns a CodecInfo object."""
    raise NotImplementedError("codecs.lookup() is not supported: Pystachy has no codec registry, and str.encode() and bytes.decode() have UTF-8, Latin-1 and ASCII")


def _forget_codec(encoding: str, /) -> None:
    pass


def strict_errors(exc: UnicodeError) -> tuple[str, int]:
    raise exc


def _handler_unsupported(name: str) -> None:
    raise NotImplementedError("codecs." + name + "() is not supported: Pystachy's UnicodeError has no start, end and object attributes")


def ignore_errors(exc: UnicodeError) -> tuple[str, int]:
    _handler_unsupported("ignore_errors")
    return ("", 0)


def replace_errors(exc: UnicodeError) -> tuple[str, int]:
    _handler_unsupported("replace_errors")
    return ("", 0)


def xmlcharrefreplace_errors(exc: UnicodeError) -> tuple[str, int]:
    _handler_unsupported("xmlcharrefreplace_errors")
    return ("", 0)


def backslashreplace_errors(exc: UnicodeError) -> tuple[str, int]:
    _handler_unsupported("backslashreplace_errors")
    return ("", 0)


def namereplace_errors(exc: UnicodeError) -> tuple[str, int]:
    _handler_unsupported("namereplace_errors")
    return ("", 0)


def _surrogateescape(exc: UnicodeError) -> tuple[str, int]:
    _handler_unsupported("lookup_error('surrogateescape')")
    return ("", 0)


def _surrogatepass(exc: UnicodeError) -> tuple[str, int]:
    _handler_unsupported("lookup_error('surrogatepass')")
    return ("", 0)


def lookup_error(name: str, /) -> Callable[[UnicodeError], tuple[str, int]]:
    """lookup_error(errors) -> handler

Return the error handler for the specified error handling name or raise
a LookupError, if no handler exists under this name."""
    if name in _handlers:
        return _handlers[name]
    if name == "strict":
        return strict_errors
    if name == "ignore":
        return ignore_errors
    if name == "replace":
        return replace_errors
    if name == "xmlcharrefreplace":
        return xmlcharrefreplace_errors
    if name == "backslashreplace":
        return backslashreplace_errors
    if name == "namereplace":
        return namereplace_errors
    if name == "surrogateescape":
        return _surrogateescape
    if name == "surrogatepass":
        return _surrogatepass
    raise LookupError("unknown error handler name '" + name + "'")


def register_error(errors: str, handler: Callable[[UnicodeError], tuple[str, int]], /) -> None:
    """Register the specified error handler under the name errors.

handler must be a callable object, that will be called with an exception
instance containing information about the location of the
encoding/decoding error and must return a (replacement, new position)
tuple."""
    # (str.encode() and bytes.decode() take only the builtin handlers' names)
    _handlers[errors] = handler


def _unregister_error(errors: str, /) -> bool:
    if errors in _BUILTIN_HANDLERS:
        raise ValueError("cannot un-register built-in error handler '" + errors + "'")
    if errors in _handlers:
        del _handlers[errors]
        return True
    return False


def _unsupported(name: str) -> None:
    raise NotImplementedError("codecs." + name + "() is not supported: Pystachy's codecs are UTF-8, Latin-1, ASCII and charmap")


def utf_7_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    _unsupported("utf_7_encode")
    return (b"", 0)


def utf_7_decode(data: bytes, errors: str | None = None, final: bool = False, /) -> tuple[str, int]:
    _unsupported("utf_7_decode")
    return ("", 0)


def utf_16_encode(s: str, errors: str | None = None, byteorder: int = 0, /) -> tuple[bytes, int]:
    _unsupported("utf_16_encode")
    return (b"", 0)


def utf_16_le_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    _unsupported("utf_16_le_encode")
    return (b"", 0)


def utf_16_be_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    _unsupported("utf_16_be_encode")
    return (b"", 0)


def utf_16_decode(data: bytes, errors: str | None = None, final: bool = False, /) -> tuple[str, int]:
    _unsupported("utf_16_decode")
    return ("", 0)


def utf_16_le_decode(data: bytes, errors: str | None = None, final: bool = False, /) -> tuple[str, int]:
    _unsupported("utf_16_le_decode")
    return ("", 0)


def utf_16_be_decode(data: bytes, errors: str | None = None, final: bool = False, /) -> tuple[str, int]:
    _unsupported("utf_16_be_decode")
    return ("", 0)


def utf_16_ex_decode(data: bytes, errors: str | None = None, byteorder: int = 0, final: bool = False, /) -> tuple[str, int, int]:
    _unsupported("utf_16_ex_decode")
    return ("", 0, 0)


def utf_32_encode(s: str, errors: str | None = None, byteorder: int = 0, /) -> tuple[bytes, int]:
    _unsupported("utf_32_encode")
    return (b"", 0)


def utf_32_le_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    _unsupported("utf_32_le_encode")
    return (b"", 0)


def utf_32_be_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    _unsupported("utf_32_be_encode")
    return (b"", 0)


def utf_32_decode(data: bytes, errors: str | None = None, final: bool = False, /) -> tuple[str, int]:
    _unsupported("utf_32_decode")
    return ("", 0)


def utf_32_le_decode(data: bytes, errors: str | None = None, final: bool = False, /) -> tuple[str, int]:
    _unsupported("utf_32_le_decode")
    return ("", 0)


def utf_32_be_decode(data: bytes, errors: str | None = None, final: bool = False, /) -> tuple[str, int]:
    _unsupported("utf_32_be_decode")
    return ("", 0)


def utf_32_ex_decode(data: bytes, errors: str | None = None, byteorder: int = 0, final: bool = False, /) -> tuple[str, int, int]:
    _unsupported("utf_32_ex_decode")
    return ("", 0, 0)


def unicode_escape_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    _unsupported("unicode_escape_encode")
    return (b"", 0)


def unicode_escape_decode(data: bytes, errors: str | None = None, final: bool = True, /) -> tuple[str, int]:
    _unsupported("unicode_escape_decode")
    return ("", 0)


def raw_unicode_escape_encode(s: str, errors: str | None = None, /) -> tuple[bytes, int]:
    _unsupported("raw_unicode_escape_encode")
    return (b"", 0)


def raw_unicode_escape_decode(data: bytes, errors: str | None = None, final: bool = True, /) -> tuple[str, int]:
    _unsupported("raw_unicode_escape_decode")
    return ("", 0)


def escape_encode(data: bytes, errors: str | None = None, /) -> tuple[bytes, int]:
    _unsupported("escape_encode")
    return (b"", 0)


def escape_decode(data: bytes, errors: str | None = None, /) -> tuple[bytes, int]:
    _unsupported("escape_decode")
    return (b"", 0)
