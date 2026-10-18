"""Native recursive JSON values and a bounded JSON text codec.

This prototype implements loads(str) and dumps(JSONValue). Integers use Pystachy's
signed 64-bit range, nesting is limited to 256 containers, and object keys are str.
Decoder hooks, bytes input, encoder subclasses, indentation and file APIs are not
implemented. Containers are created with recursive JSONValue storage; narrowing
keeps their original identity and mutable contents.
"""

type JSONValue = None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]

__all__ = ["loads", "dumps", "JSONDecodeError", "JSONValue"]


class JSONDecodeError(ValueError):
    """Invalid JSON text, with a character offset and one-based line and column."""

    def __init__(self, msg: str, doc: str, pos: int) -> None:
        self.msg: str = msg
        self.doc: str = doc
        self.pos: int = pos
        self.lineno: int = doc.count("\n", 0, pos) + 1
        self.colno: int = pos - doc.rfind("\n", 0, pos)
        super().__init__(f"{msg}: line {self.lineno} column {self.colno} (char {pos})")


def _digit(c: str) -> bool:
    return "0" <= c <= "9"


class _Parser:
    def __init__(self, doc: str) -> None:
        self.doc = doc
        self.pos = 0
        self.n = len(doc)

    def skip(self) -> None:
        while self.pos < self.n and self.doc[self.pos] in " \t\n\r":
            self.pos += 1

    def hex4(self, at: int) -> int:
        # at names the 'u', which is CPython's error position for this escape.
        if at + 4 >= self.n:
            raise JSONDecodeError("Invalid \\uXXXX escape", self.doc, at)
        value = 0
        for i in range(at + 1, at + 5):
            c = self.doc[i]
            if "0" <= c <= "9":
                digit = ord(c) - 48
            elif "a" <= c <= "f":
                digit = ord(c) - 87
            elif "A" <= c <= "F":
                digit = ord(c) - 55
            else:
                raise JSONDecodeError("Invalid \\uXXXX escape", self.doc, at)
            value = value * 16 + digit
        return value

    def string(self) -> str:
        begin = self.pos
        self.pos += 1
        start = self.pos
        chunks: list[str] = []
        while self.pos < self.n:
            c = self.doc[self.pos]
            if c == '"':
                chunks.append(self.doc[start:self.pos])
                self.pos += 1
                return "".join(chunks)
            if ord(c) < 32:
                raise JSONDecodeError("Invalid control character at", self.doc, self.pos)
            if c != "\\":
                self.pos += 1
                continue
            chunks.append(self.doc[start:self.pos])
            slash = self.pos
            self.pos += 1
            if self.pos == self.n:
                break
            esc = self.doc[self.pos]
            self.pos += 1
            if esc == '"' or esc == "\\" or esc == "/":
                chunks.append(esc)
            elif esc == "b":
                chunks.append("\b")
            elif esc == "f":
                chunks.append("\f")
            elif esc == "n":
                chunks.append("\n")
            elif esc == "r":
                chunks.append("\r")
            elif esc == "t":
                chunks.append("\t")
            elif esc == "u":
                cp = self.hex4(self.pos - 1)
                self.pos += 4
                if 0xD800 <= cp <= 0xDBFF and self.doc[self.pos:self.pos + 2] == "\\u":
                    low = self.hex4(self.pos + 1)
                    if 0xDC00 <= low <= 0xDFFF:
                        cp = 0x10000 + ((cp - 0xD800) << 10) + low - 0xDC00
                        self.pos += 6
                chunks.append(chr(cp))
            else:
                raise JSONDecodeError("Invalid \\escape", self.doc, slash)
            start = self.pos
        raise JSONDecodeError("Unterminated string starting at", self.doc, begin)

    def number(self) -> JSONValue:
        start = self.pos
        i = start
        if self.doc[i] == "-":
            i += 1
        if i >= self.n or not _digit(self.doc[i]):
            raise JSONDecodeError("Expecting value", self.doc, start)
        if self.doc[i] == "0":
            i += 1
        else:
            while i < self.n and _digit(self.doc[i]):
                i += 1
        real = False
        if i + 1 < self.n and self.doc[i] == "." and _digit(self.doc[i + 1]):
            real = True
            i += 2
            while i < self.n and _digit(self.doc[i]):
                i += 1
        if i < self.n and self.doc[i] in "eE":
            end = i + 1
            if end < self.n and self.doc[end] in "+-":
                end += 1
            if end < self.n and _digit(self.doc[end]):
                real = True
                i = end + 1
                while i < self.n and _digit(self.doc[i]):
                    i += 1
        self.pos = i
        token = self.doc[start:i]
        if real:
            return float(token)
        digits = token[1:] if token.startswith("-") else token
        bound = "9223372036854775808" if token.startswith("-") else "9223372036854775807"
        if len(digits) > 19 or (len(digits) == 19 and digits > bound):
            raise OverflowError("JSON integer exceeds signed 64-bit range")
        return int(token)

    def array(self, depth: int) -> list[JSONValue]:
        self.pos += 1
        self.skip()
        out: list[JSONValue] = []
        if self.pos < self.n and self.doc[self.pos] == "]":
            self.pos += 1
            return out
        while True:
            out.append(self.value(depth + 1))
            self.skip()
            if self.pos < self.n and self.doc[self.pos] == "]":
                self.pos += 1
                return out
            if self.pos == self.n or self.doc[self.pos] != ",":
                raise JSONDecodeError("Expecting ',' delimiter", self.doc, self.pos)
            comma = self.pos
            self.pos += 1
            self.skip()
            if self.pos < self.n and self.doc[self.pos] == "]":
                raise JSONDecodeError("Illegal trailing comma before end of array", self.doc, comma)

    def object(self, depth: int) -> dict[str, JSONValue]:
        self.pos += 1
        self.skip()
        out: dict[str, JSONValue] = {}
        if self.pos < self.n and self.doc[self.pos] == "}":
            self.pos += 1
            return out
        while True:
            if self.pos == self.n or self.doc[self.pos] != '"':
                raise JSONDecodeError("Expecting property name enclosed in double quotes", self.doc, self.pos)
            key = self.string()
            self.skip()
            if self.pos == self.n or self.doc[self.pos] != ":":
                raise JSONDecodeError("Expecting ':' delimiter", self.doc, self.pos)
            self.pos += 1
            self.skip()
            out[key] = self.value(depth + 1)
            self.skip()
            if self.pos < self.n and self.doc[self.pos] == "}":
                self.pos += 1
                return out
            if self.pos == self.n or self.doc[self.pos] != ",":
                raise JSONDecodeError("Expecting ',' delimiter", self.doc, self.pos)
            comma = self.pos
            self.pos += 1
            self.skip()
            if self.pos < self.n and self.doc[self.pos] == "}":
                raise JSONDecodeError("Illegal trailing comma before end of object", self.doc, comma)

    def value(self, depth: int) -> JSONValue:
        if self.pos == self.n:
            raise JSONDecodeError("Expecting value", self.doc, self.pos)
        c = self.doc[self.pos]
        if c == '"':
            return self.string()
        if c == "[" or c == "{":
            if depth >= 256:
                raise RecursionError("maximum JSON nesting depth exceeded")
            if c == "[":
                return self.array(depth)
            return self.object(depth)
        if self.doc[self.pos:self.pos + 4] == "null":
            self.pos += 4
            return None
        if self.doc[self.pos:self.pos + 4] == "true":
            self.pos += 4
            return True
        if self.doc[self.pos:self.pos + 5] == "false":
            self.pos += 5
            return False
        if self.doc[self.pos:self.pos + 3] == "NaN":
            self.pos += 3
            return float("nan")
        if self.doc[self.pos:self.pos + 8] == "Infinity":
            self.pos += 8
            return float("inf")
        if self.doc[self.pos:self.pos + 9] == "-Infinity":
            self.pos += 9
            return -float("inf")
        if c == "-" or _digit(c):
            return self.number()
        raise JSONDecodeError("Expecting value", self.doc, self.pos)


def loads(s: str) -> JSONValue:
    """Decode JSON text into recursive native values (signed 64-bit integers)."""
    if s.startswith("\ufeff"):
        raise JSONDecodeError("Unexpected UTF-8 BOM (decode using utf-8-sig)", s, 0)
    parser = _Parser(s)
    parser.skip()
    value = parser.value(0)
    parser.skip()
    if parser.pos != parser.n:
        raise JSONDecodeError("Extra data", s, parser.pos)
    return value


def _quote(s: str, ensure_ascii: bool) -> str:
    out: list[str] = ['"']
    for c in s:
        cp = ord(c)
        if c == '"' or c == "\\":
            out.append("\\" + c)
        elif c == "\b":
            out.append("\\b")
        elif c == "\f":
            out.append("\\f")
        elif c == "\n":
            out.append("\\n")
        elif c == "\r":
            out.append("\\r")
        elif c == "\t":
            out.append("\\t")
        elif cp < 32 or (ensure_ascii and cp >= 127):
            if cp <= 0xFFFF:
                out.append("\\u" + format(cp, "04x"))
            else:
                cp -= 0x10000
                out.append("\\u" + format(0xD800 + (cp >> 10), "04x"))
                out.append("\\u" + format(0xDC00 + (cp & 1023), "04x"))
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


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
            self.out.append(_quote(value, self.ascii))
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
                self.out.append(_quote(key, self.ascii))
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
