"""Bounded JSON wire codec for the typed native-agent example.

Nodes use integer child indices instead of heterogeneous Python containers.
Numbers remain lexemes: this codec does not silently round provider metadata.
It rejects duplicate keys and unpaired escaped UTF-16 surrogates.
"""

MAX_JSON_TEXT = 1_048_576
MAX_JSON_DEPTH = 32


def utf8_size(text: str) -> int:
    """Validate Unicode scalars and count UTF-8 bytes in both execution modes."""
    if len("é") == 2:
        # Native strings expose individual UTF-8 bytes; validate before parsing
        # or quoting any file, provider response, or tool output.
        position = 0
        while position < len(text):
            lead = ord(text[position])
            width = 1
            if lead < 128:
                pass
            elif 0xC2 <= lead <= 0xDF:
                width = 2
            elif 0xE0 <= lead <= 0xEF:
                width = 3
            elif 0xF0 <= lead <= 0xF4:
                width = 4
            else:
                raise ValueError("invalid UTF-8 leading byte")
            if position + width > len(text):
                raise ValueError("incomplete UTF-8 sequence")
            for offset in range(1, width):
                continuation = ord(text[position + offset])
                if continuation < 0x80 or continuation > 0xBF:
                    raise ValueError("invalid UTF-8 continuation byte")
            if width > 1:
                second = ord(text[position + 1])
                if (lead == 0xE0 and second < 0xA0) or (lead == 0xED and second >= 0xA0):
                    raise ValueError("UTF-8 sequence is not a Unicode scalar")
                if (lead == 0xF0 and second < 0x90) or (lead == 0xF4 and second >= 0x90):
                    raise ValueError("UTF-8 sequence is outside the Unicode range")
            position += width
        return len(text)
    size = 0
    for c in text:
        codepoint = ord(c)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise ValueError("unpaired Unicode surrogate")
        if codepoint < 128:
            size += 1
        elif codepoint < 0x800:
            size += 2
        elif codepoint < 0x10000:
            size += 3
        else:
            size += 4
    return size


class JsonNode:
    def __init__(self, kind: str, value: str, start: int, end: int) -> None:
        self.kind = kind
        self.value = value
        self.start = start
        self.end = end
        self.keys: list[str] = []
        self.children: list[int] = []
        self._keys_seen: set[str] = set()


class JsonDocument:
    def __init__(self, text: str) -> None:
        if utf8_size(text) > MAX_JSON_TEXT:
            raise ValueError("JSON input exceeds the size limit")
        self.text = text
        self.position = 0
        self.nodes: list[JsonNode] = []
        self.root = self._value(0)
        self._space()
        if self.position != len(self.text):
            raise ValueError("trailing content after JSON value")

    def _space(self) -> None:
        while self.position < len(self.text):
            c = self.text[self.position]
            if c != " " and c != "\t" and c != "\r" and c != "\n":
                break
            self.position += 1

    def _hex4(self) -> int:
        end = self.position + 4
        if end > len(self.text):
            raise ValueError("incomplete JSON Unicode escape")
        digits = self.text[self.position : end]
        for c in digits:
            if c not in "0123456789abcdefABCDEF":
                raise ValueError("invalid JSON Unicode escape")
        self.position = end
        return int(digits, 16)

    def _string_value(self) -> str:
        # The opening quote has already been checked by the caller.
        self.position += 1
        segment = self.position
        parts: list[str] = []
        while self.position < len(self.text):
            c = self.text[self.position]
            if c == '"':
                parts.append(self.text[segment : self.position])
                self.position += 1
                return "".join(parts)
            if ord(c) < 32:
                raise ValueError("unescaped control character in JSON string")
            if c != "\\":
                self.position += 1
                continue
            parts.append(self.text[segment : self.position])
            self.position += 1
            if self.position >= len(self.text):
                raise ValueError("incomplete JSON string escape")
            escaped = self.text[self.position]
            self.position += 1
            if escaped == '"' or escaped == "\\" or escaped == "/":
                parts.append(escaped)
            elif escaped == "b":
                parts.append("\b")
            elif escaped == "f":
                parts.append("\f")
            elif escaped == "n":
                parts.append("\n")
            elif escaped == "r":
                parts.append("\r")
            elif escaped == "t":
                parts.append("\t")
            elif escaped == "u":
                codepoint = self._hex4()
                if 0xD800 <= codepoint <= 0xDBFF:
                    if self.text[self.position : self.position + 2] != "\\u":
                        raise ValueError("unpaired JSON high surrogate")
                    self.position += 2
                    low = self._hex4()
                    if low < 0xDC00 or low > 0xDFFF:
                        raise ValueError("invalid JSON surrogate pair")
                    codepoint = 0x10000 + (codepoint - 0xD800) * 1024 + low - 0xDC00
                elif 0xDC00 <= codepoint <= 0xDFFF:
                    raise ValueError("unpaired JSON low surrogate")
                # Pystachy's chr(<256) creates a byte; %c produces Unicode UTF-8.
                parts.append("%c" % codepoint)
            else:
                raise ValueError("invalid JSON string escape")
            segment = self.position
        raise ValueError("unterminated JSON string")

    def _number(self) -> str:
        start = self.position
        if self.text[self.position] == "-":
            self.position += 1
        if self.position >= len(self.text):
            raise ValueError("incomplete JSON number")
        c = self.text[self.position]
        if c == "0":
            self.position += 1
        elif c in "123456789":
            self.position += 1
            while self.position < len(self.text) and self.text[self.position] in "0123456789":
                self.position += 1
        else:
            raise ValueError("invalid JSON number")
        if self.position < len(self.text) and self.text[self.position] == ".":
            self.position += 1
            digits = self.position
            while self.position < len(self.text) and self.text[self.position] in "0123456789":
                self.position += 1
            if self.position == digits:
                raise ValueError("JSON fraction requires digits")
        if self.position < len(self.text) and self.text[self.position] in "eE":
            self.position += 1
            if self.position < len(self.text) and self.text[self.position] in "+-":
                self.position += 1
            digits = self.position
            while self.position < len(self.text) and self.text[self.position] in "0123456789":
                self.position += 1
            if self.position == digits:
                raise ValueError("JSON exponent requires digits")
        return self.text[start : self.position]

    def _value(self, depth: int) -> int:
        if depth > MAX_JSON_DEPTH:
            raise ValueError("JSON nesting exceeds the depth limit")
        self._space()
        start = self.position
        if start >= len(self.text):
            raise ValueError("expected a JSON value")
        c = self.text[start]
        if (c == "{" or c == "[") and depth >= MAX_JSON_DEPTH:
            raise ValueError("JSON nesting exceeds the depth limit")
        node = JsonNode("null", "", start, start)
        index = len(self.nodes)
        self.nodes.append(node)
        if c == "{" or c == "[":
            is_object = c == "{"
            node.kind = "object" if is_object else "array"
            close = "}" if is_object else "]"
            self.position += 1
            self._space()
            if self.position < len(self.text) and self.text[self.position] == close:
                self.position += 1
            else:
                while True:
                    if is_object:
                        if self.position >= len(self.text) or self.text[self.position] != '"':
                            raise ValueError("JSON object key must be a string")
                        key = self._string_value()
                        if key in node._keys_seen:
                            raise ValueError("duplicate JSON object key")
                        node._keys_seen.add(key)
                        node.keys.append(key)
                        self._space()
                        if self.position >= len(self.text) or self.text[self.position] != ":":
                            raise ValueError("expected colon after JSON key")
                        self.position += 1
                    node.children.append(self._value(depth + 1))
                    self._space()
                    if self.position >= len(self.text):
                        raise ValueError("unterminated JSON container")
                    delimiter = self.text[self.position]
                    self.position += 1
                    if delimiter == close:
                        break
                    if delimiter != ",":
                        raise ValueError("expected comma in JSON container")
                    self._space()
        elif c == '"':
            node.kind = "string"
            node.value = self._string_value()
        elif c == "-" or c in "0123456789":
            node.kind = "number"
            node.value = self._number()
        elif self.text[start : start + 4] == "true":
            node.kind = "bool"
            node.value = "true"
            self.position += 4
        elif self.text[start : start + 5] == "false":
            node.kind = "bool"
            node.value = "false"
            self.position += 5
        elif self.text[start : start + 4] == "null":
            self.position += 4
        else:
            raise ValueError("invalid JSON value")
        node.end = self.position
        return index

    def _node(self, index: int) -> JsonNode:
        if index < 0 or index >= len(self.nodes):
            raise ValueError("missing JSON value")
        return self.nodes[index]

    def field(self, node: int, key: str) -> int:
        value = self._node(node)
        if value.kind != "object":
            raise ValueError("expected a JSON object")
        for i in range(len(value.keys)):
            if value.keys[i] == key:
                return value.children[i]
        return -1

    def string(self, node: int) -> str:
        value = self._node(node)
        if value.kind != "string":
            raise ValueError("expected a JSON string")
        return value.value

    def items(self, node: int) -> list[int]:
        value = self._node(node)
        if value.kind != "array":
            raise ValueError("expected a JSON array")
        return value.children

    def object_fields(self, node: int) -> list[str]:
        value = self._node(node)
        if value.kind != "object":
            raise ValueError("expected a JSON object")
        return value.keys

    def raw(self, node: int) -> str:
        value = self._node(node)
        return self.text[value.start : value.end]


def json_quote(text: str) -> str:
    utf8_size(text)
    parts: list[str] = ['"']
    for c in text:
        if c == '"':
            parts.append('\\"')
        elif c == "\\":
            parts.append("\\\\")
        elif ord(c) < 32:
            parts.append("\\u%04x" % ord(c))
        else:
            parts.append(c)
    parts.append('"')
    return "".join(parts)
