# pystachy: identity-inert
"""Native recursive JSON values and a bounded JSON text codec.

This prototype implements loads(str), dumps(JSONValue) and the default JSONDecoder.
Typed JSONValue integers use Pystachy's signed 64-bit range; the dynamic Any
decoder promotes larger tokens. Decoding nests as CPython's C decoder does, 9,998 containers at
any recursion limit. Encoding counts against sys.setrecursionlimit() and stops at 2,000
containers, which keeps a raised limit within the native stack; object keys are str.
load(fp) and dump(obj, fp) read and write a text file's whole document. Decoder hooks, bytes
input and encoder subclasses are not implemented. Containers are created with recursive
JSONValue storage; narrowing keeps their original identity and mutable contents.
"""

from typing import TextIO

from _pystachy_bytescan import scan as _scan_bytes

type JSONValue = None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]

__all__ = ["load", "loads", "dump", "dumps", "JSONDecoder", "JSONDecodeError", "JSONValue"]


class JSONDecodeError(ValueError):
    """Invalid JSON text, with a character offset and one-based line and column."""

    def __init__(self, msg: str, doc: str, pos: int) -> None:
        self.msg: str = msg
        self.doc: str = doc
        self.pos: int = pos
        self.lineno: int = doc.count("\n", 0, pos) + 1
        self.colno: int = pos - doc.rfind("\n", 0, pos)
        super().__init__(f"{msg}: line {self.lineno} column {self.colno} (char {pos})")


def _u8char(data: bytes, i: int) -> int:
    # The character at data[i] as Pystachy's str counts characters: a UTF-8 sequence (surrogates
    # included), else the one byte, the character of its value; as its bytes << 21 | its code point.
    c = data[i]
    k = 1 if c < 0xC2 or c > 0xF4 else 2 if c < 0xE0 else 3 if c < 0xF0 else 4
    if k == 1 or i + k > len(data):
        return 1 << 21 | c
    value = c & (0x7F >> k)
    for j in range(i + 1, i + k):
        d = data[j]
        if (d & 0xC0) != 0x80:
            return 1 << 21 | c
        value = (value << 6) | (d & 0x3F)
    if value < (0x80 if k == 2 else 0x800 if k == 3 else 0x10000) or value > 0x10FFFF:
        return 1 << 21 | c
    return k << 21 | value


def _u8len(data: bytes, i: int) -> int:
    # The bytes of the character at data[i] (_u8char).
    return _u8char(data, i) >> 21


def _u8next(data: bytes, i: int, n: int) -> int:
    # Where the character at data[i] ends, i + _u8len(data, i) of n = len(data) bytes, without
    # computing its code point: a lead byte and continuation bytes of a code point its length
    # holds (a surrogate's too) are one character; anything else is left to _u8len.
    c = data[i]
    if c < 0x80:
        return i + 1
    if c >= 0xC2 and c < 0xE0:
        if i + 1 < n and (data[i + 1] & 0xC0) == 0x80:
            return i + 2
    elif c >= 0xE0 and c < 0xF0:
        if i + 2 < n and (data[i + 1] & 0xC0) == 0x80 and (data[i + 2] & 0xC0) == 0x80 and (c != 0xE0 or data[i + 1] >= 0xA0):
            return i + 3
    elif c >= 0xF0 and c <= 0xF4:
        if (i + 3 < n and (data[i + 1] & 0xC0) == 0x80 and (data[i + 2] & 0xC0) == 0x80 and (data[i + 3] & 0xC0) == 0x80
                and (c != 0xF0 or data[i + 1] >= 0x90) and (c != 0xF4 or data[i + 1] < 0x90)):
            return i + 4
    return i + _u8len(data, i)


# The first 64 nested containers are decoded by calls, which sys.setrecursionlimit() counts, and
# deeper ones with the open containers on a list (deep()), up to CPython's bound: its C decoder
# accepts 9,998 nested containers on Linux (its C recursion limit), whatever the recursion limit.
# (The two numbers are literals where they are used, here and in _pystachy_json_any: a module
# variable that another module reads is not identity-inert.)
_STRING_TOKEN = b'"'
_ARRAY_TOKEN = b"["
_OBJECT_TOKEN = b"{"


_NO_KEY_BYTES: list[bytes] = []  # (never filled: key() replaces them)
_NO_KEY_STRS: list[str] = []


class _Parser:
    # The scanner reads the text's UTF-8 bytes: indexing bytes yields integers, without a
    # one-character string or a code-point offset per step. Every delimiter, digit and escape
    # is ASCII, so the parser stops only at character boundaries; error() converts such a
    # byte offset into the character offset that CPython reports.
    def __init__(self, doc: str, raw: bool) -> None:
        self.doc = doc
        self.lone = False
        try:
            self.data: bytes = doc.encode()
        except UnicodeEncodeError:
            # A str may hold lone surrogates: surrogatepass keeps each as its three bytes.
            self.data = doc.encode("utf-8", "surrogatepass")
            self.lone = True
        # raw: the text holds bytes that are not UTF-8, which Pystachy reads from files,
        # input() and sys.argv without checking them; strings are then slices of doc.
        self.raw = raw
        self.plain: bool = not raw and not self.lone  # decode() alone makes each string
        self.pos = 0
        self.n = len(self.data)
        self.mark_byte = 0  # where char_index() last counted to, as the parser moves forward
        self.mark_char = 0
        # Recently decoded object keys by length and first byte, made at the first key;
        # records of one shape repeat their keys, which then share one str (as CPython's
        # decoder memo shares them). Until then both hold shared empty lists.
        self.key_bytes: list[bytes] = _NO_KEY_BYTES
        self.key_strs: list[str] = _NO_KEY_STRS

    def char_index(self, at: int) -> int:
        # The characters before byte offset at, counted on from the offset asked before.
        if at < self.mark_byte:
            self.mark_byte = 0
            self.mark_char = 0
        data = self.data
        n = self.n
        i = self.mark_byte
        count = self.mark_char
        while i < at:
            if data[i] < 0x80:
                i += 1
            else:
                i = _u8next(data, i, n)
            count += 1
        self.mark_byte = i
        self.mark_char = count
        return count

    def seek_char(self, idx: int) -> None:
        # raw_decode's idx is a character offset; the scanner itself uses byte offsets.
        if idx < 0:
            raise ValueError("idx cannot be negative")
        data = self.data
        n = self.n
        i = 0
        count = 0
        while count < idx and i < n:
            if data[i] < 0x80:
                i += 1
            else:
                i = _u8next(data, i, n)
            count += 1
        if count < idx:
            raise JSONDecodeError("Expecting value", self.doc, idx)
        self.pos = i
        self.mark_byte = i
        self.mark_char = count

    def text(self, start: int, end: int) -> str:
        # Without lone surrogates, decode() needs no error handler or codec name lookup.
        if self.plain:
            return self.data[start:end].decode()
        return self.decoded(self.data[start:end], start, end)

    def decoded(self, raw: bytes, start: int, end: int) -> str:
        # The str of raw, which is data[start:end].
        if self.plain:
            return raw.decode()
        if self.lone and not self.raw:
            return raw.decode("utf-8", "surrogatepass")
        return self.doc[self.char_index(start):self.char_index(end)]

    def error(self, msg: str, at: int) -> JSONDecodeError:
        return JSONDecodeError(msg, self.doc, self.char_index(at))

    def skip(self) -> None:
        data = self.data
        n = len(data)
        i = self.pos
        while i < n:
            c = data[i]
            if c > 32 or (c != 32 and c != 9 and c != 10 and c != 13):
                break
            i += 1
        self.pos = i

    # The dynamic decoder uses the scanner through typed, identity-inert boundaries.
    # Keep numeric cursor fields private to these methods; direct external observations
    # are still accepted and make the compiler restore identity tracking for the module.
    def next_token(self) -> bytes:
        if self.pos == self.n:
            raise self.error("Expecting value", self.pos)
        token = self.data[self.pos]
        # Canonical byte tokens let the caller compare identities without indexing,
        # allocating a string or borrowing numeric identity from the scanner.
        return _STRING_TOKEN if token == 34 else _ARRAY_TOKEN if token == 91 else _OBJECT_TOKEN if token == 123 else b" "

    def scalar(self) -> JSONValue:
        return self.value(0)

    def scalar_value(self) -> JSONValue:
        # The Any decoder has already ruled out strings and containers. Keep this
        # dispatch independent of value() so an Any-only decoder does not pull in
        # typed recursive containers. Number scanning remains shared in number();
        # an overflowing integer is returned as its token, for the Any decoder
        # to promote without changing the scanner's fixed-width cursor arithmetic.
        i = self.pos
        if i == self.n:
            raise self.error("Expecting value", i)
        data = self.data
        c = data[i]
        if 48 <= c <= 57:
            return self.number(True)
        if c == 45:
            if data.startswith(b"-Infinity", i):
                self.pos = i + 9
                return -float("inf")
            return self.number(True)
        if c == 110 and data.startswith(b"null", i):
            self.pos = i + 4
            return None
        if c == 116 and data.startswith(b"true", i):
            self.pos = i + 4
            return True
        if c == 102 and data.startswith(b"false", i):
            self.pos = i + 5
            return False
        if c == 78 and data.startswith(b"NaN", i):
            self.pos = i + 3
            return float("nan")
        if c == 73 and data.startswith(b"Infinity", i):
            self.pos = i + 8
            return float("inf")
        raise self.error("Expecting value", i)

    def begin(self, array: bool) -> bool:
        close = 93 if array else 125
        self.pos += 1
        self.skip()
        if self.pos < self.n and self.data[self.pos] == close:
            self.pos += 1
            return True
        return False

    def next_item(self, array: bool) -> bool:
        close = 93 if array else 125
        self.skip()
        i = self.pos
        if i == self.n:
            raise self.error("Expecting ',' delimiter", i)
        token = self.data[i]
        if token == close:
            self.pos = i + 1
            return False
        if token != 44:
            raise self.error("Expecting ',' delimiter", i)
        self.pos = i + 1
        self.skip()
        if self.pos < self.n and self.data[self.pos] == close:
            raise self.error("Illegal trailing comma before end of " + ("array" if array else "object"), i)
        return True

    def object_key(self) -> str:
        i = self.pos
        if i == self.n or self.data[i] != 34:
            raise self.error("Expecting property name enclosed in double quotes", i)
        key = self.key()
        self.skip()
        i = self.pos
        if i == self.n or self.data[i] != 58:
            raise self.error("Expecting ':' delimiter", i)
        self.pos = i + 1
        self.skip()
        return key

    # begin(), next_item() and object_key() again, for the decoders of deeply nested containers
    # (deep() and _pystachy_json_any._deep()). They are copies and not second callers, and
    # deep_key() scans with escaped(), which every string with an escape already calls: a
    # helper with one caller is inlined into the Any decoder's loops, and one with two was
    # not, which cost 5% of the instructions of decoding small documents.
    def deep_token(self) -> bytes:
        # next_token()'s token of a container that comes next, else b" " (also at the end of the
        # text, where the value's own decoder raises). A token and not a number: a number that
        # an Any decoder takes from here would need its identity tracked.
        i = self.pos
        if i < self.n:
            c = self.data[i]
            if c == 91:
                return _ARRAY_TOKEN
            if c == 123:
                return _OBJECT_TOKEN
        return b" "

    def deep_begin(self, array: bool) -> bool:
        close = 93 if array else 125
        self.pos += 1
        self.skip()
        if self.pos < self.n and self.data[self.pos] == close:
            self.pos += 1
            return True
        return False

    def deep_next(self, array: bool) -> bool:
        close = 93 if array else 125
        self.skip()
        i = self.pos
        if i == self.n:
            raise self.error("Expecting ',' delimiter", i)
        token = self.data[i]
        if token == close:
            self.pos = i + 1
            return False
        if token != 44:
            raise self.error("Expecting ',' delimiter", i)
        self.pos = i + 1
        self.skip()
        if self.pos < self.n and self.data[self.pos] == close:
            raise self.error("Illegal trailing comma before end of " + ("array" if array else "object"), i)
        return True

    def deep_key(self) -> str:
        i = self.pos
        if i == self.n or self.data[i] != 34:
            raise self.error("Expecting property name enclosed in double quotes", i)
        key = self.escaped(i, i + 1)
        self.skip()
        i = self.pos
        if i == self.n or self.data[i] != 58:
            raise self.error("Expecting ':' delimiter", i)
        self.pos = i + 1
        self.skip()
        return key

    def start_document(self) -> None:
        if self.n >= 3 and self.data[0] == 0xEF and self.data[1] == 0xBB and self.data[2] == 0xBF:
            raise JSONDecodeError("Unexpected UTF-8 BOM (decode using utf-8-sig)", self.doc, 0)
        self.skip()

    def end_document(self) -> None:
        self.skip()
        if self.pos != self.n:
            raise self.error("Extra data", self.pos)

    def hex4(self, at: int) -> int:
        # at names the 'u', which is CPython's error position for this escape.
        if at + 4 >= self.n:
            raise self.error("Invalid \\uXXXX escape", at)
        data = self.data
        value = 0
        for i in range(at + 1, at + 5):
            c = data[i]
            if 48 <= c <= 57:
                digit = c - 48
            elif 97 <= c <= 102:
                digit = c - 87
            elif 65 <= c <= 70:
                digit = c - 55
            else:
                raise self.error("Invalid \\uXXXX escape", at)
            value = value * 16 + digit
        return value

    # Strings are scanned in one of two ways. A scalar loop over the whole string needs no setup,
    # so object keys and every string of a text of at most 1 KiB use plain_end(). A longer text
    # may hold strings long enough to repay a call of the bulk byte scanner: its string values
    # scan a 32-byte scalar prefix (plain_prefix()) and continue past it with plain_rest(). A
    # bound on the scalar loop costs some instructions for every string and every byte, which
    # short strings in short texts never repay (bench/smoke/README.md's JSON decoder controls).
    def plain_end(self, begin: int) -> int:
        # The closing quote of the string that begins at begin when no escape or control
        # character comes first; else -1 - the offset where the scan stopped (or the end).
        data = self.data
        n = len(data)
        i = begin + 1
        while i < n:
            c = data[i]
            # One comparison and a check for a backslash pass most ordinary bytes ('#' and above).
            if c < 35 or c == 92:
                if c == 34:
                    return i
                if c == 92 or c < 32:
                    return -1 - i
            i += 1
        return -1 - n

    def plain_prefix(self, begin: int) -> int:
        # plain_end() for a string of at most 32 bytes: else -1 - the offset where the scan
        # stopped (an escape, a control character, the end, or the 33rd byte of the string).
        data = self.data
        n = len(data)
        i = begin + 1
        limit = i + 33  # (32 ordinary bytes and the closing quote)
        if limit > n:
            limit = n + 0  # a scalar cursor, without borrowing n's numeric identity
        while i < limit:
            c = data[i]
            if c < 35 or c == 92:
                if c == 34:
                    return i
                if c == 92 or c < 32:
                    return -1 - i
            i += 1
        return -1 - i

    def plain_rest(self, i: int) -> int:
        # Continues an ordinary run at i with the bulk byte scanner: the closing quote, else
        # -1 - the offset where the run ended (an escape, a control character or the end).
        # string() and escaped() share it, which keeps the native call out of line.
        data = self.data
        n = len(data)
        if i < n:
            c = data[i]
            if c != 92 and c >= 32:
                i = _scan_bytes(data, i, n, 34, 92, 32)
                if i < n and data[i] == 34:
                    return i
        return -1 - i

    def string(self) -> str:
        # Most strings have no escape: one slice of the bytes is the result.
        begin = self.pos
        if len(self.data) > 1024:
            end = self.plain_prefix(begin)
            if end < 0:
                end = self.plain_rest(-1 - end)
        else:
            end = self.plain_end(begin)
        if end < 0:
            return self.escaped(begin, -1 - end)
        self.pos = end + 1
        return self.text(begin + 1, end)

    def key(self) -> str:
        # An object key: a key equal to one seen before in this document returns its str.
        begin = self.pos
        end = self.plain_end(begin)
        if end < 0:
            return self.escaped(begin, -1 - end)
        self.pos = end + 1
        if not self.key_bytes:
            self.key_bytes = [b""] * 64
            self.key_strs = [""] * 64
        data = self.data
        size = end - begin - 1
        slot = (size * 31 + data[begin + 1]) & 63
        known = self.key_bytes[slot]
        if len(known) == size and data.startswith(known, begin + 1):
            return self.key_strs[slot]
        raw = data[begin + 1:end]
        text = self.decoded(raw, begin + 1, end)
        self.key_bytes[slot] = raw
        self.key_strs[slot] = text
        return text

    def escaped(self, begin: int, i: int) -> str:
        # The rest of the string that begins at begin, from where its scan stopped: its
        # first backslash, a control character or the end of the text.
        data = self.data
        n = len(data)
        start = begin + 1
        chunks: list[str] = []
        while i < n:
            c = data[i]
            if c == 34:
                if i > start:
                    chunks.append(self.text(start, i))
                self.pos = i + 1
                return "".join(chunks)
            if c < 32:
                raise self.error("Invalid control character at", i)
            if c != 92:
                i += 1
                continue
            # A long ordinary run before this escape predicts another after it: bulk-scan
            # that one. Dense escapes keep the byte loop, without a per-byte bound check.
            long_run = i - start >= 16
            if i > start:
                chunks.append(self.text(start, i))
            slash = i
            i += 1
            if i == n:
                break
            esc = data[i]
            i += 1
            if esc == 34:
                chunks.append('"')
            elif esc == 92:
                chunks.append("\\")
            elif esc == 47:
                chunks.append("/")
            elif esc == 98:
                chunks.append("\b")
            elif esc == 102:
                chunks.append("\f")
            elif esc == 110:
                chunks.append("\n")
            elif esc == 114:
                chunks.append("\r")
            elif esc == 116:
                chunks.append("\t")
            elif esc == 117:
                cp = self.hex4(i - 1)
                i += 4
                if 0xD800 <= cp <= 0xDBFF and i + 1 < n and data[i] == 92 and data[i + 1] == 117:
                    low = self.hex4(i + 1)
                    if 0xDC00 <= low <= 0xDFFF:
                        cp = 0x10000 + ((cp - 0xD800) << 10) + low - 0xDC00
                        i += 6
                chunks.append(chr(cp))
            else:
                raise self.error("Invalid \\escape", slash)
            start = i
            if long_run:
                end = self.plain_rest(i)
                i = end if end >= 0 else -1 - end
        raise self.error("Unterminated string starting at", begin)

    def number(self, wide: bool = False) -> JSONValue:
        data = self.data
        n = len(data)
        start = self.pos
        i = start
        negative = data[i] == 45
        if negative:
            i += 1
        if i >= n or not 48 <= data[i] <= 57:
            raise self.error("Expecting value", start)
        first = i
        value = data[i] - 48
        i += 1
        if value != 0:
            while i < n:
                c = data[i]
                if c < 48 or c > 57:
                    break
                if i - first < 18:  # (18 digits cannot overflow)
                    value = value * 10 + c - 48
                i += 1
        digits = i - first
        real = False
        if i + 1 < n and data[i] == 46 and 48 <= data[i + 1] <= 57:
            real = True
            i += 2
            while i < n and 48 <= data[i] <= 57:
                i += 1
        if i < n and (data[i] == 101 or data[i] == 69):
            end = i + 1
            if end < n and (data[end] == 43 or data[end] == 45):
                end += 1
            if end < n and 48 <= data[end] <= 57:
                real = True
                i = end + 1
                while i < n and 48 <= data[i] <= 57:
                    i += 1
        self.pos = i
        if real:
            return float(data[start:i].decode())
        if digits > 18:
            token = data[first:i].decode()
            bound = "9223372036854775808" if negative else "9223372036854775807"
            if digits > 19 or token > bound:
                if wide:
                    return data[start:i].decode()
                raise OverflowError("JSON integer exceeds signed 64-bit range")
            return int(data[start:i].decode())
        return -value if negative else value

    def array(self, depth: int) -> list[JSONValue]:
        data = self.data
        self.pos += 1
        self.skip()
        out: list[JSONValue] = []
        if self.pos < self.n and data[self.pos] == 93:
            self.pos += 1
            return out
        while True:
            out.append(self.value(depth + 1))
            self.skip()
            i = self.pos
            if i == self.n:
                raise self.error("Expecting ',' delimiter", i)
            token = data[i]
            if i < self.n and token == 93:
                self.pos = i + 1
                return out
            if token != 44:
                raise self.error("Expecting ',' delimiter", i)
            self.pos = i + 1
            self.skip()
            if self.pos < self.n and data[self.pos] == 93:
                raise self.error("Illegal trailing comma before end of array", i)

    def object(self, depth: int) -> dict[str, JSONValue]:
        data = self.data
        self.pos += 1
        self.skip()
        out: dict[str, JSONValue] = {}
        if self.pos < self.n and data[self.pos] == 125:
            self.pos += 1
            return out
        while True:
            i = self.pos
            if i == self.n or data[i] != 34:
                raise self.error("Expecting property name enclosed in double quotes", i)
            key = self.key()
            self.skip()
            i = self.pos
            if i == self.n or data[i] != 58:
                raise self.error("Expecting ':' delimiter", i)
            self.pos = i + 1
            self.skip()
            out[key] = self.value(depth + 1)
            self.skip()
            i = self.pos
            if i == self.n:
                raise self.error("Expecting ',' delimiter", i)
            token = data[i]
            if i < self.n and token == 125:
                self.pos = i + 1
                return out
            if token != 44:
                raise self.error("Expecting ',' delimiter", i)
            self.pos = i + 1
            self.skip()
            if self.pos < self.n and data[self.pos] == 125:
                raise self.error("Illegal trailing comma before end of object", i)

    def deep(self, array: bool, depth: int) -> JSONValue:
        # The container at depth and all that it holds, with the open containers on lists where
        # array() and object() have them in calls. It stops where CPython's decoder does.
        arrays: list[bool] = []
        lists: list[list[JSONValue]] = []
        dicts: list[dict[str, JSONValue]] = []
        keys: list[str] = []
        while True:
            # open a container of the kind array says
            if depth >= 9998:
                raise RecursionError("maximum recursion depth exceeded while decoding a JSON "
                                     + ("array" if array else "object") + " from a unicode string")
            arrays.append(array)
            if array:
                opened: list[JSONValue] = []
                lists.append(opened)
            else:
                mapping: dict[str, JSONValue] = {}
                dicts.append(mapping)
            depth += 1
            more = not self.deep_begin(array)
            while True:
                array = arrays[-1]
                if more:
                    key = "" if array else self.deep_key()
                    opener = self.deep_token()
                    if opener is _ARRAY_TOKEN or opener is _OBJECT_TOKEN:
                        keys.append(key)
                        array = opener is _ARRAY_TOKEN
                        break
                    item = self.value(depth)  # (no container: a scalar, or the error for none)
                    if array:
                        lists[-1].append(item)
                    else:
                        dicts[-1][key] = item
                else:
                    # the innermost container is closed: it is the value, or an item of the one around it
                    arrays.pop()
                    depth -= 1
                    done: JSONValue = lists.pop() if array else dicts.pop()
                    if len(arrays) == 0:
                        return done
                    array = arrays[-1]
                    if array:
                        lists[-1].append(done)
                    else:
                        dicts[-1][keys[-1]] = done
                    keys.pop()
                more = self.deep_next(array)

    def value(self, depth: int) -> JSONValue:
        i = self.pos
        if i == self.n:
            raise self.error("Expecting value", i)
        data = self.data
        c = data[i]
        if c == 34:
            return self.string()
        if c == 123 or c == 91:
            # Each nested container is two calls that sys.setrecursionlimit() counts (value(),
            # then array() or object()), for the first 64: deep() decodes the ones nested
            # further, with neither calls nor the native stack.
            if depth >= 64:
                return self.deep(c == 91, depth)
            if c == 91:
                return self.array(depth)
            return self.object(depth)
        if 48 <= c <= 57:
            return self.number()
        if c == 45:
            if data.startswith(b"-Infinity", i):
                self.pos = i + 9
                return -float("inf")
            return self.number()
        if c == 110 and data.startswith(b"null", i):
            self.pos = i + 4
            return None
        if c == 116 and data.startswith(b"true", i):
            self.pos = i + 4
            return True
        if c == 102 and data.startswith(b"false", i):
            self.pos = i + 5
            return False
        if c == 78 and data.startswith(b"NaN", i):
            self.pos = i + 3
            return float("nan")
        if c == 73 and data.startswith(b"Infinity", i):
            self.pos = i + 8
            return float("inf")
        raise self.error("Expecting value", i)


def loads(s: str) -> JSONValue:
    """Decode JSON text into recursive native values (signed 64-bit integers)."""
    try:
        return _parse(_Parser(s, False))
    except UnicodeDecodeError:
        # s holds bytes that are not UTF-8, which decode() rejects: parse it again, taking
        # each string from s itself, as Pystachy's str counts characters.
        return _parse(_Parser(s, True))




def load(fp: TextIO) -> JSONValue:
    """Decode the JSON text that fp.read() returns, as loads() does."""
    return loads(fp.read())


class JSONDecoder:
    """Default JSON decoder; custom hooks and strict=False are not supported."""

    def decode(self, s: str) -> JSONValue:
        # Match JSONDecoder's overridable raw_decode call, including its effects
        # and exceptions. The base raw_decode handles its own decoding retry;
        # retrying here could execute a user override twice.
        n = len(s)
        idx = 0
        while idx < n and s[idx] in " \t\n\r":
            idx += 1
        value, end = self.raw_decode(s, idx=idx)
        # CPython's whitespace regex clamps its starting position to the input.
        # A custom raw_decode may return an offset outside that range.
        end = min(max(end, 0), n)
        while end < n and s[end] in " \t\n\r":
            end += 1
        if end != n:
            raise JSONDecodeError("Extra data", s, end)
        return value

    def raw_decode(self, s: str, idx: int = 0) -> tuple[JSONValue, int]:
        return _raw_decode(s, idx)


def _raw_decode(s: str, idx: int = 0) -> tuple[JSONValue, int]:
    # Native adapter entry point. Like JSONDecoder.raw_decode(), this starts exactly
    # at idx and permits trailing text. Opt-in calls can select Any's containers.
    try:
        return _raw_parse(_Parser(s, False), idx)
    except UnicodeDecodeError:
        return _raw_parse(_Parser(s, True), idx)


def _raw_parse(parser: _Parser, idx: int) -> tuple[JSONValue, int]:
    parser.seek_char(idx)
    value = parser.value(0)
    return value, parser.char_index(parser.pos)


def _parse(parser: _Parser, reject_bom: bool = True) -> JSONValue:
    data = parser.data
    if reject_bom and parser.n >= 3 and data[0] == 0xEF and data[1] == 0xBB and data[2] == 0xBF:
        # U+FEFF's UTF-8 bytes; s.startswith() would count the characters of all of s
        raise JSONDecodeError("Unexpected UTF-8 BOM (decode using utf-8-sig)", parser.doc, 0)
    parser.skip()
    value = parser.value(0)
    parser.skip()
    if parser.pos != parser.n:
        raise parser.error("Extra data", parser.pos)
    return value


# (Both tables are displays of constants: building them as the module loads, by joining digits,
# cost each program that imports json about 95,000 instructions.)
# a byte's two hex digits
_HEX2: list[str] = [
    "00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "0a", "0b", "0c", "0d", "0e", "0f",
    "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "1a", "1b", "1c", "1d", "1e", "1f",
    "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "2a", "2b", "2c", "2d", "2e", "2f",
    "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "3a", "3b", "3c", "3d", "3e", "3f",
    "40", "41", "42", "43", "44", "45", "46", "47", "48", "49", "4a", "4b", "4c", "4d", "4e", "4f",
    "50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "5a", "5b", "5c", "5d", "5e", "5f",
    "60", "61", "62", "63", "64", "65", "66", "67", "68", "69", "6a", "6b", "6c", "6d", "6e", "6f",
    "70", "71", "72", "73", "74", "75", "76", "77", "78", "79", "7a", "7b", "7c", "7d", "7e", "7f",
    "80", "81", "82", "83", "84", "85", "86", "87", "88", "89", "8a", "8b", "8c", "8d", "8e", "8f",
    "90", "91", "92", "93", "94", "95", "96", "97", "98", "99", "9a", "9b", "9c", "9d", "9e", "9f",
    "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "aa", "ab", "ac", "ad", "ae", "af",
    "b0", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "ba", "bb", "bc", "bd", "be", "bf",
    "c0", "c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "ca", "cb", "cc", "cd", "ce", "cf",
    "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9", "da", "db", "dc", "dd", "de", "df",
    "e0", "e1", "e2", "e3", "e4", "e5", "e6", "e7", "e8", "e9", "ea", "eb", "ec", "ed", "ee", "ef",
    "f0", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "fa", "fb", "fc", "fd", "fe", "ff",
]
# The escapes of the ASCII characters that need one: control characters, '"', '\\' and, with
# ensure_ascii, DEL; the others' entries are unused.
_ESCAPES: list[str] = [
    "\\u0000", "\\u0001", "\\u0002", "\\u0003", "\\u0004", "\\u0005", "\\u0006", "\\u0007",
    "\\b", "\\t", "\\n", "\\u000b", "\\f", "\\r", "\\u000e", "\\u000f",
    "\\u0010", "\\u0011", "\\u0012", "\\u0013", "\\u0014", "\\u0015", "\\u0016", "\\u0017",
    "\\u0018", "\\u0019", "\\u001a", "\\u001b", "\\u001c", "\\u001d", "\\u001e", "\\u001f",
    "\\u0020", "\\u0021", "\\\"", "\\u0023", "\\u0024", "\\u0025", "\\u0026", "\\u0027",
    "\\u0028", "\\u0029", "\\u002a", "\\u002b", "\\u002c", "\\u002d", "\\u002e", "\\u002f",
    "\\u0030", "\\u0031", "\\u0032", "\\u0033", "\\u0034", "\\u0035", "\\u0036", "\\u0037",
    "\\u0038", "\\u0039", "\\u003a", "\\u003b", "\\u003c", "\\u003d", "\\u003e", "\\u003f",
    "\\u0040", "\\u0041", "\\u0042", "\\u0043", "\\u0044", "\\u0045", "\\u0046", "\\u0047",
    "\\u0048", "\\u0049", "\\u004a", "\\u004b", "\\u004c", "\\u004d", "\\u004e", "\\u004f",
    "\\u0050", "\\u0051", "\\u0052", "\\u0053", "\\u0054", "\\u0055", "\\u0056", "\\u0057",
    "\\u0058", "\\u0059", "\\u005a", "\\u005b", "\\\\", "\\u005d", "\\u005e", "\\u005f",
    "\\u0060", "\\u0061", "\\u0062", "\\u0063", "\\u0064", "\\u0065", "\\u0066", "\\u0067",
    "\\u0068", "\\u0069", "\\u006a", "\\u006b", "\\u006c", "\\u006d", "\\u006e", "\\u006f",
    "\\u0070", "\\u0071", "\\u0072", "\\u0073", "\\u0074", "\\u0075", "\\u0076", "\\u0077",
    "\\u0078", "\\u0079", "\\u007a", "\\u007b", "\\u007c", "\\u007d", "\\u007e", "\\u007f",
]


def _quote(out: list[str], s: str, ensure_ascii: bool) -> None:
    # Appends s as a JSON string. One scan of its UTF-8 bytes finds whether a character needs an
    # escape; most strings need none, and go between the quotes whole (encode() returns a str's
    # own storage unless it holds a character from U+D000 to U+DFFF, and rejects lone surrogates).
    try:
        data = s.encode()
    except UnicodeEncodeError:
        _escape_chars(out, s, ensure_ascii)
        return
    i = 0
    for b in data:
        if b < 32 or b == 34 or b == 92 or (ensure_ascii and b >= 127):
            if ensure_ascii:
                _escape_bytes(out, data, i)
            else:
                _escape_chars(out, s, False)
            return
        i += 1
    out.append('"')
    out.append(s)
    out.append('"')


def _escape(out: list[str], cp: int) -> None:
    # Appends the escape of code point cp: one past U+FFFF is its UTF-16 surrogate pair, and
    # each \uXXXX goes in three pieces that need no new string
    if cp < 128:
        out.append(_ESCAPES[cp])
        return
    if cp > 0xFFFF:
        cp -= 0x10000
        _escape(out, 0xD800 + (cp >> 10))
        cp = 0xDC00 + (cp & 1023)
    out.append("\\u")
    out.append(_HEX2[cp >> 8])
    out.append(_HEX2[cp & 255])


def _escape_bytes(out: list[str], data: bytes, i: int) -> None:
    # The ensure_ascii form of the text of UTF-8 bytes data, whose first i bytes are printable
    # ASCII but '"' and '\\': a run of those is one slice, and each other character an escape. A
    # byte that starts no UTF-8 sequence (in text Pystachy read without checking it) is the
    # character of its value, as str counts it (_u8char).
    out.append('"')
    n = len(data)
    start = 0
    while i < n:
        b = data[i]
        if b >= 32 and b < 127 and b != 34 and b != 92:
            i += 1
            continue
        if start < i:
            out.append(data[start:i].decode())
        c = _u8char(data, i)
        _escape(out, c & 0x1FFFFF)
        i += c >> 21
        start = i
    if start < n:
        out.append(data[start:n].decode())
    out.append('"')


def _escape_chars(out: list[str], s: str, ensure_ascii: bool) -> None:
    # s character by character, without ensure_ascii or where it holds lone surrogates: a run of
    # characters that need no escape is one slice
    out.append('"')
    start = 0
    i = 0
    for c in s:
        cp = ord(c)
        if cp < 32 or cp == 34 or cp == 92 or (ensure_ascii and cp >= 127):
            if start < i:
                out.append(s[start:i])
            _escape(out, cp)
            start = i + 1
        i += 1
    if start < i:
        out.append(s[start:i])
    out.append('"')


def _indent_text(indent: JSONValue) -> str:
    # one level of dumps()'s indent: the str itself, or that many spaces (none for 0 or less),
    # as CPython makes it, ' ' * indent. (dumps() takes the indent as a JSONValue: an int or a
    # str in the one type that a module that tracks no numeric identity may take, dynamic.py's
    # identity_inert, where int | str holds an int with its object)
    if isinstance(indent, str):
        return indent
    if isinstance(indent, bool):
        return " " if indent else ""
    if isinstance(indent, int):
        return " " * indent
    if indent is None:
        return ""
    kind = "float" if isinstance(indent, float) else "list" if isinstance(indent, list) else "dict"
    raise TypeError("can't multiply sequence by non-int of type '" + kind + "'")


class _Encoder:
    def __init__(self, ensure_ascii: bool, allow_nan: bool, sort_keys: bool,
                 item_separator: str, key_separator: str, pretty: bool, indent: str, calls: int) -> None:
        self.ascii = ensure_ascii
        self.nan = allow_nan
        self.sort_keys = sort_keys
        self.item_separator = item_separator
        self.key_separator = key_separator
        self.pretty = pretty  # (an indent was given: each item goes on its own line)
        self.indent = indent
        # (how many nested containers are a call of write() each: the deeper ones are deep()'s)
        self.calls = calls
        self.out: list[str] = []
        self.lists: list[list[JSONValue]] = []
        self.dicts: list[dict[str, JSONValue]] = []

    def write(self, value: JSONValue, depth: int) -> None:
        if value is None:
            self.out.append("null")
        elif isinstance(value, bool):
            self.out.append("true" if value else "false")
        elif isinstance(value, int):
            self.out.append(str(value))
        elif isinstance(value, float):
            if value != value or value == float("inf") or value == -float("inf"):
                if not self.nan:
                    raise ValueError("Out of range float values are not JSON compliant: " + repr(value))
                self.out.append("NaN" if value != value else "Infinity" if value > 0.0 else "-Infinity")
            else:
                self.out.append(repr(value))
        elif isinstance(value, str):
            _quote(self.out, value, self.ascii)
        elif isinstance(value, list):
            if depth >= self.calls:
                self.deep(value, depth)
                return
            for list_parent in self.lists:
                if value is list_parent:
                    raise ValueError("Circular reference detected")
            if depth >= 2000:  # (dump()'s bound: one call for each container, within the native stack)
                raise RecursionError("maximum recursion depth exceeded while encoding a JSON object")
            self.lists.append(value)
            self.out.append("[")
            separator = self.item_separator
            if self.pretty and len(value) > 0:
                # (CPython writes an empty container on one line, with or without an indent)
                inner = "\n" + self.indent * (depth + 1)
                separator += inner
                self.out.append(inner)
            first = True
            for item in value:
                if not first:
                    self.out.append(separator)
                first = False
                self.write(item, depth + 1)
            if self.pretty and len(value) > 0:
                self.out.append("\n" + self.indent * depth)
            self.out.append("]")
            self.lists.pop()
        elif isinstance(value, dict):
            if depth >= self.calls:
                self.deep(value, depth)
                return
            for dict_parent in self.dicts:
                if value is dict_parent:
                    raise ValueError("Circular reference detected")
            if depth >= 2000:  # (dump()'s bound: one call for each container, within the native stack)
                raise RecursionError("maximum recursion depth exceeded while encoding a JSON object")
            self.dicts.append(value)
            self.out.append("{")
            keys = sorted(value) if self.sort_keys else list(value)
            separator = self.item_separator
            if self.pretty and len(keys) > 0:
                inner = "\n" + self.indent * (depth + 1)
                separator += inner
                self.out.append(inner)
            first = True
            for key in keys:
                if not first:
                    self.out.append(separator)
                first = False
                _quote(self.out, key, self.ascii)
                self.out.append(self.key_separator)
                self.write(value[key], depth + 1)
            if self.pretty and len(keys) > 0:
                self.out.append("\n" + self.indent * depth)
            self.out.append("}")
            self.dicts.pop()

    def deep(self, value: JSONValue, depth: int) -> None:
        # The container at depth and all that it holds, as write() writes them, with the open
        # containers on lists where write() has them in its calls: nesting then counts against
        # neither the recursion limit nor the native stack, and stops where CPython's C encoder
        # does, at 9,998 containers. That encoder counts a container before it looks for a
        # circular reference, and so does this.
        out = self.out
        opened: set[int] = set()
        for list_parent in self.lists:
            opened.add(id(list_parent))
        for dict_parent in self.dicts:
            opened.add(id(dict_parent))
        arrays: list[bool] = []
        lists: list[list[JSONValue]] = []
        dicts: list[dict[str, JSONValue]] = []
        keys: list[list[str]] = []
        at: list[int] = []
        separators: list[str] = []
        while True:
            if isinstance(value, list):
                if depth >= 9998:
                    raise RecursionError("maximum recursion depth exceeded while encoding a JSON object")
                if id(value) in opened:
                    raise ValueError("Circular reference detected")
                opened.add(id(value))
                arrays.append(True)
                lists.append(value)
                at.append(0)
                out.append("[")
                depth += 1
                if self.pretty:
                    inner = "\n" + self.indent * depth
                    separators.append(self.item_separator + inner)
                    if len(value) > 0:
                        out.append(inner)
            elif isinstance(value, dict):
                if depth >= 9998:
                    raise RecursionError("maximum recursion depth exceeded while encoding a JSON object")
                if id(value) in opened:
                    raise ValueError("Circular reference detected")
                opened.add(id(value))
                arrays.append(False)
                dicts.append(value)
                keys.append(sorted(value) if self.sort_keys else list(value))
                at.append(0)
                out.append("{")
                depth += 1
                if self.pretty:
                    inner = "\n" + self.indent * depth
                    separators.append(self.item_separator + inner)
                    if len(value) > 0:
                        out.append(inner)
            elif value is None:
                # (a scalar, as write() writes it: a call of write() here would make the two one
                # recursion, and its ordinary path the slower for it)
                out.append("null")
            elif isinstance(value, bool):
                out.append("true" if value else "false")
            elif isinstance(value, int):
                out.append(str(value))
            elif isinstance(value, float):
                if value != value or value == float("inf") or value == -float("inf"):
                    if not self.nan:
                        raise ValueError("Out of range float values are not JSON compliant: " + repr(value))
                    out.append("NaN" if value != value else "Infinity" if value > 0.0 else "-Infinity")
                else:
                    out.append(repr(value))
            elif isinstance(value, str):
                _quote(out, value, self.ascii)
            # the next value to write: the next item of the innermost open container that has
            # one, after closing those that have none
            while True:
                if len(arrays) == 0:
                    return
                i = at[-1]
                if arrays[-1]:
                    items = lists[-1]
                    if i < len(items):
                        if i > 0:
                            out.append(separators[-1] if self.pretty else self.item_separator)
                        at[-1] = i + 1
                        value = items[i]
                        break
                    if self.pretty and i > 0:
                        out.append("\n" + self.indent * (depth - 1))
                    out.append("]")
                    opened.discard(id(items))
                    lists.pop()
                else:
                    names = keys[-1]
                    if i < len(names):
                        if i > 0:
                            out.append(separators[-1] if self.pretty else self.item_separator)
                        at[-1] = i + 1
                        _quote(out, names[i], self.ascii)
                        out.append(self.key_separator)
                        value = dicts[-1][names[i]]
                        break
                    if self.pretty and i > 0:
                        out.append("\n" + self.indent * (depth - 1))
                    out.append("}")
                    opened.discard(id(dicts[-1]))
                    dicts.pop()
                    keys.pop()
                arrays.pop()
                at.pop()
                if self.pretty:
                    separators.pop()
                depth -= 1


def dumps(obj: JSONValue, *, ensure_ascii: bool = True, allow_nan: bool = True,
          sort_keys: bool = False, indent: JSONValue = None,
          separators: tuple[str, str] | None = None) -> str:
    """Encode recursive JSON values; mutable container identity is preserved."""
    item_separator = ", " if indent is None else ","  # (an indented line ends without a space)
    key_separator = ": "
    if separators is not None:
        item_separator = separators[0]
        key_separator = separators[1]
    # (as CPython's C encoder, which nests 9,998 containers whatever the recursion limit: the
    # first 64 are a call each)
    encoder = _Encoder(ensure_ascii, allow_nan, sort_keys, item_separator, key_separator, indent is not None,
                       _indent_text(indent), 64)
    encoder.write(obj, 0)
    return "".join(encoder.out)


def dump(obj: JSONValue, fp: TextIO, *, ensure_ascii: bool = True, allow_nan: bool = True,
         sort_keys: bool = False, indent: JSONValue = None,
         separators: tuple[str, str] | None = None) -> None:
    """Write the text dumps() returns to fp (one write, where CPython writes it in pieces)."""
    item_separator = ", " if indent is None else ","
    key_separator = ": "
    if separators is not None:
        item_separator = separators[0]
        key_separator = separators[1]
    # (as CPython's dump(), whose encoder is Python code: every container is a call, which the
    # recursion limit bounds)
    encoder = _Encoder(ensure_ascii, allow_nan, sort_keys, item_separator, key_separator, indent is not None,
                       _indent_text(indent), 2001)
    encoder.write(obj, 0)
    fp.write("".join(encoder.out))
