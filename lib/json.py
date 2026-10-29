# pystachy: identity-inert
"""Native recursive JSON values and a bounded JSON text codec.

This prototype implements loads(str), dumps(JSONValue) and the default JSONDecoder.
Integers use Pystachy's
signed 64-bit range, nesting is limited to 256 containers, and object keys are str.
Decoder hooks, bytes input, encoder subclasses, indentation and file APIs are not
implemented. Containers are created with recursive JSONValue storage; narrowing
keeps their original identity and mutable contents.
"""

type JSONValue = None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]

__all__ = ["loads", "dumps", "JSONDecoder", "JSONDecodeError", "JSONValue"]


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
        i = self.mark_byte
        count = self.mark_char
        while i < at:
            i += _u8len(data, i)
            count += 1
        self.mark_byte = i
        self.mark_char = count
        return count

    def seek_char(self, idx: int) -> None:
        # raw_decode's idx is a character offset; the scanner itself uses byte offsets.
        if idx < 0:
            raise ValueError("idx cannot be negative")
        i = 0
        count = 0
        while count < idx and i < self.n:
            i += _u8len(self.data, i)
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
    def next_token(self) -> str:
        if self.pos == self.n:
            raise self.error("Expecting value", self.pos)
        token = self.data[self.pos]
        return '"' if token == 34 else "[" if token == 91 else "{" if token == 123 else ""

    def scalar(self) -> JSONValue:
        return self.value(0)

    def begin(self, close: bytes) -> bool:
        self.pos += 1
        self.skip()
        if self.pos < self.n and self.data[self.pos] == close[0]:
            self.pos += 1
            return True
        return False

    def next_item(self, close: bytes, kind: str) -> bool:
        self.skip()
        i = self.pos
        if i < self.n and self.data[i] == close[0]:
            self.pos = i + 1
            return False
        if i == self.n or self.data[i] != 44:
            raise self.error("Expecting ',' delimiter", i)
        self.pos = i + 1
        self.skip()
        if self.pos < self.n and self.data[self.pos] == close[0]:
            raise self.error("Illegal trailing comma before end of " + kind, i)
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

    def plain_end(self, begin: int) -> int:
        # The closing quote of the string that begins at begin when no escape or control
        # character comes first; else -1 - the offset where the scan stopped (or the end).
        data = self.data
        n = len(data)
        i = begin + 1
        while i < n:
            c = data[i]
            if c == 34:
                return i
            if c == 92 or c < 32:
                return -1 - i
            i += 1
        return -1 - n

    def string(self) -> str:
        # Most strings have no escape: one slice of the bytes is the result.
        begin = self.pos
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
        # The rest of the string that begins at begin, from where plain_end() stopped: its
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
        raise self.error("Unterminated string starting at", begin)

    def number(self) -> JSONValue:
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
            if i < self.n and data[i] == 93:
                self.pos = i + 1
                return out
            if i == self.n or data[i] != 44:
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
            if i < self.n and data[i] == 125:
                self.pos = i + 1
                return out
            if i == self.n or data[i] != 44:
                raise self.error("Expecting ',' delimiter", i)
            self.pos = i + 1
            self.skip()
            if self.pos < self.n and data[self.pos] == 125:
                raise self.error("Illegal trailing comma before end of object", i)

    def value(self, depth: int) -> JSONValue:
        i = self.pos
        if i == self.n:
            raise self.error("Expecting value", i)
        data = self.data
        c = data[i]
        if c == 34:
            return self.string()
        if c == 123 or c == 91:
            if depth >= 256:
                raise RecursionError("maximum JSON nesting depth exceeded")
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


_HEX = "0123456789abcdef"
_HEX2: list[str] = [_HEX[i >> 4] + _HEX[i & 15] for i in range(256)]  # (a byte's two hex digits)
# The escapes of the ASCII characters that need one: control characters, '"', '\\' and, with
# ensure_ascii, DEL; the others' entries are unused.
_ESCAPES: list[str] = ["\\u00" + _HEX2[c] for c in range(128)]
_ESCAPES[8] = "\\b"
_ESCAPES[9] = "\\t"
_ESCAPES[10] = "\\n"
_ESCAPES[12] = "\\f"
_ESCAPES[13] = "\\r"
_ESCAPES[34] = "\\\""
_ESCAPES[92] = "\\\\"


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


class _Encoder:
    def __init__(self, ensure_ascii: bool, allow_nan: bool, sort_keys: bool,
                 item_separator: str, key_separator: str) -> None:
        self.ascii = ensure_ascii
        self.nan = allow_nan
        self.sort_keys = sort_keys
        self.item_separator = item_separator
        self.key_separator = key_separator
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
            for list_parent in self.lists:
                if value is list_parent:
                    raise ValueError("Circular reference detected")
            if depth >= 256:
                raise RecursionError("maximum JSON nesting depth exceeded")
            self.lists.append(value)
            self.out.append("[")
            first = True
            for item in value:
                if not first:
                    self.out.append(self.item_separator)
                first = False
                self.write(item, depth + 1)
            self.out.append("]")
            self.lists.pop()
        elif isinstance(value, dict):
            for dict_parent in self.dicts:
                if value is dict_parent:
                    raise ValueError("Circular reference detected")
            if depth >= 256:
                raise RecursionError("maximum JSON nesting depth exceeded")
            self.dicts.append(value)
            self.out.append("{")
            keys = sorted(value) if self.sort_keys else list(value)
            first = True
            for key in keys:
                if not first:
                    self.out.append(self.item_separator)
                first = False
                _quote(self.out, key, self.ascii)
                self.out.append(self.key_separator)
                self.write(value[key], depth + 1)
            self.out.append("}")
            self.dicts.pop()


def dumps(obj: JSONValue, *, ensure_ascii: bool = True, allow_nan: bool = True,
          sort_keys: bool = False, separators: tuple[str, str] | None = None) -> str:
    """Encode recursive JSON values; mutable container identity is preserved."""
    item_separator = ", "
    key_separator = ": "
    if separators is not None:
        item_separator = separators[0]
        key_separator = separators[1]
    encoder = _Encoder(ensure_ascii, allow_nan, sort_keys, item_separator, key_separator)
    encoder.write(obj, 0)
    return "".join(encoder.out)
