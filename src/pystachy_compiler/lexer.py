"""Lexer component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.diagnostics import LINES, fail
from src.pystachy_compiler.utils import codec, normcodec


KEYWORDS: dict[str, bool] = {}
for _k in "False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield".split():
    KEYWORDS[_k] = True
OPS: list[str] = "**= //= >>= <<= -> ** // == != <= >= += -= *= /= %= &= |= ^= @= << >> := ... + - * / % < > = ( ) [ ] { } , : . ; & | ^ ~ @".split()
ESCAPES: dict[str, str] = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


def utf8(c: int) -> str:
    # the UTF-8 bytes of code point c, one character per byte (strings are byte strings)
    if c < 128:
        return chr(c)
    if c < 2048:
        return chr(192 | (c >> 6)) + chr(128 | (c & 63))
    if c < 65536:
        return chr(224 | (c >> 12)) + chr(128 | ((c >> 6) & 63)) + chr(128 | (c & 63))
    return chr(240 | (c >> 18)) + chr(128 | ((c >> 12) & 63)) + chr(128 | ((c >> 6) & 63)) + chr(128 | (c & 63))


def utf8len(s: str, i: int) -> int:
    # the length of the UTF-8 sequence at s[i] (a character per byte), as CPython's valid_utf8
    # checks it (no overlong form, surrogate or code point past U+10FFFF); if it is not valid,
    # minus the number of its bytes that are (0: not even the first)
    c = ord(s[i])
    if c < 128:
        return 1
    n = 3 if c >= 240 and c < 245 else (2 if c >= 224 and c < 240 else (1 if c >= 194 and c < 224 else 0))
    lo = 160 if c == 224 else (144 if c == 240 else 128)
    hi = 159 if c == 237 else (143 if c == 244 else 191)
    for k in range(1, n + 1):
        d = ord(s[i + k]) if i + k < len(s) else 0
        if d < lo or d > hi:
            return -k
        lo = 128
        hi = 191
    return 0 if n == 0 else n + 1


def utf8_error(s: str) -> str:
    # what CPython's UTF-8 codec says of bytes s (a character per byte), "" if they are UTF-8
    i = 0
    while i < len(s):
        k = utf8len(s, i)
        if k > 0:
            i += k
            continue
        why = "invalid start byte" if k == 0 else ("unexpected end of data" if i - k >= len(s) else "invalid continuation byte")
        at = f"byte 0x{ord(s[i]):02x} in position {i}" if k >= -1 else f"bytes in position {i}-{i - k - 1}"
        return f"'utf-8' codec can't decode {at}: {why}"
    return ""


def codepoint(s: str, i: int) -> int:
    # the code point of the valid UTF-8 sequence at s[i]
    c = ord(s[i])
    n = utf8len(s, i)
    if n == 1:
        return c
    v = c & (31 if n == 2 else (15 if n == 3 else 7))
    for k in range(1, n):
        v = (v << 6) | (ord(s[i + k]) & 63)
    return v


# code points that cannot be in an identifier, as first-last pairs: CPython's "invalid
# non-printable character" (spaces, controls, format characters, private use) and its "invalid
# character" (the blocks of punctuation and symbols). Other non-ASCII characters may be letters.
NONPRINT: list[int] = [0x80, 0xA0, 0xAD, 0xAD, 0x600, 0x605, 0x61C, 0x61C, 0x6DD, 0x6DD, 0x70F, 0x70F, 0x180E, 0x180E,
                       0x1680, 0x1680, 0x2000, 0x200B, 0x200E, 0x200F, 0x2028, 0x202F, 0x205F, 0x2064, 0x2066, 0x206F,
                       0x3000, 0x3000, 0xE000, 0xF8FF, 0xFEFF, 0xFEFF, 0xFFF9, 0xFFFB, 0xE0001, 0xE0001, 0xE0020, 0xE007F,
                       0xF0000, 0x10FFFF]
NOTID: list[int] = [0xA1, 0xA9, 0xAB, 0xAC, 0xAE, 0xB4, 0xB6, 0xB6, 0xB8, 0xB9, 0xBB, 0xBF, 0xD7, 0xD7, 0xF7, 0xF7,
                    0x2010, 0x2027, 0x2030, 0x203E, 0x2041, 0x2053, 0x2055, 0x205E, 0x2070, 0x2070, 0x2074, 0x207E,
                    0x2080, 0x208E, 0x20A0, 0x20C0, 0x2150, 0x215F, 0x2189, 0x218B, 0x2190, 0x2BFF, 0x2E00, 0x2E7F,
                    0x3001, 0x3004, 0x3008, 0x3020, 0x3030, 0x3030, 0x303D, 0x303F, 0xFF01, 0xFF0F, 0xFF1A, 0xFF20,
                    0xFF3B, 0xFF3E, 0xFF40, 0xFF40, 0xFF5B, 0xFF64, 0xFFE0, 0xFFEE, 0xFFFC, 0xFFFD, 0x1F000, 0x1FAFF]


def among(c: int, ranges: list[int]) -> bool:
    for k in range(0, len(ranges), 2):
        if c >= ranges[k] and c <= ranges[k + 1]:
            return True
    return False


class Tok:
    def __init__(self, kind: str, text: str, line: int):
        self.kind = kind
        self.text = text
        self.line = line
        self.esc = False  # a string literal (or bytes literal) whose escapes the parser decodes


class Lexer:
    def __init__(self, src: str, line: int):
        self.src = src
        self.i = 0
        self.line = line
        self.toks: list[Tok] = []
        self.cut = ""  # the error at the end of src, where CPython stopped reading the file (see file())
        self.cutline = 0
        self.declared = False  # a file declared UTF-8 (by a byte order mark or coding declaration)

    def add(self, kind: str, text: str) -> None:
        self.toks.append(Tok(kind, text, self.line))

    def bad(self, msg: str, line: int) -> None:
        # an error of CPython's tokenizer, which CPython meets only where its parser gets to it
        # (after the parser's errors before it): the tokens end with an "error" token there. It
        # also replaces an error of CPython's parser earlier in the file (see Parser.fail)
        if self.cut != "" and self.i >= len(self.src):
            msg = self.cut  # (at the end of what CPython could read)
            line = self.cutline
        self.toks.append(Tok("error", msg, line))
        self.i = len(self.src)

    def stop(self, msg: str, line: int) -> None:
        # an error that replaces no parser error before it: one that CPython's tokenizer reports
        # without an exception (a bad unindent, too deep an indentation, an unclosed bracket, a
        # backslash in a line) or in an f-string, or a Pystachy limitation
        self.bad(msg, line)
        if self.toks[-1].text == msg:
            self.toks[-1].kind = "stop"  # (unless bad() reported where CPython stopped reading instead)

    def file(self) -> list[Tok]:
        # the tokens of a source file. CPython decodes it as UTF-8 or in the encoding that a coding
        # declaration on its first or second line names; a Latin-1 file is read as UTF-8 (what
        # CPython's str holds), and other encodings are rejected. CPython reads the main program
        # line by line, and its tokenizer fails at the first line that holds a NUL byte or (without
        # a declaration) is not UTF-8: the tokens end there. It compiles an imported module from
        # its bytes: there a NUL byte is an error first, and invalid UTF-8 one only in a string or
        # a name (as in a file declared UTF-8).
        src = self.src
        module = self.line >= LINES
        if module and src.find(chr(0)) >= 0:
            fail("source code string cannot contain null bytes", self.line + src[: src.find(chr(0))].count("\n"))
        bom = src.startswith(chr(239) + chr(187) + chr(191))
        at = 3 if bom else 0
        cs = ""
        csline = self.line
        while cs == "" and csline < self.line + 2 and at < len(src):
            e = src.find("\n", at)
            ln = src[at:] if e < 0 else src[at : e + 1]
            j = 0
            while j < len(ln) and (ln[j] == " " or ln[j] == "\t" or ln[j] == "\f"):
                j += 1
            if j < len(ln) and ln[j] != "#" and ln[j] != "\n" and ln[j] != "\r":
                break  # (code: a declaration may only follow a comment or blank line)
            m = ln.find("coding", j)
            while cs == "" and m >= 0 and m + 6 < len(ln):
                t = m + 6
                if ln[t] == ":" or ln[t] == "=":
                    t += 1
                    while t < len(ln) and (ln[t] == " " or ln[t] == "\t"):
                        t += 1
                    b = t
                    while t < len(ln) and (ln[t].isalnum() or ln[t] == "-" or ln[t] == "_" or ln[t] == ".") and ord(ln[t]) < 128:
                        t += 1
                    cs = ln[b:t]
                m = ln.find("coding", m + 1)
            if cs == "":
                csline += 1
                at = len(src) if e < 0 else e + 1
        # CPython's names for UTF-8 and Latin-1 (get_normal_name)
        low = cs[:12].lower().replace("_", "-")
        if low == "utf-8" or low.startswith("utf-8-"):
            cs = "utf-8"
        elif low == "latin-1" or low == "iso-8859-1" or low == "iso-latin-1" or low.startswith("latin-1-") or low.startswith("iso-8859-1-") or low.startswith("iso-latin-1-"):
            cs = "iso-8859-1"
        if bom and cs != "" and cs != "utf-8":
            fail(f"encoding problem: {cs} with BOM", self.line - 1)  # (CPython's line 0)
        self.declared = bom or cs == "utf-8" or (module and cs == "")
        kind = 0 if cs == "" or cs == "utf-8" else (2 if cs == "iso-8859-1" else codec(cs))
        nm = normcodec(cs).replace(".", "_")
        if kind == 0 and nm in "ascii us_ascii 646 us cp367 csascii ibm367 iso646_us iso_ir_6 ansi_x3_4_1968 ansi_x3_4_1986 iso_646_irv_1991".split():
            kind = 3
        if kind == 0 and cs != "" and cs != "utf-8":
            fail(f"encoding problem: {cs} (Pystachy reads only UTF-8, Latin-1 and ASCII source files)", csline)
        if kind == 2:
            out: list[str] = []
            for c in src:
                out.append(c if ord(c) < 128 else utf8(ord(c)))
            src = "".join(out)
            self.src = src
        elif kind == 1 and utf8_error(src) != "":
            # (CPython's codec decodes the whole file)
            fail(utf8_error(src) if module else f"encoding problem: {cs}", csline)
        elif kind == 3:
            for k in range(len(src)):
                if ord(src[k]) >= 128:
                    fail(f"'ascii' codec can't decode byte 0x{ord(src[k]):02x} in position {k}: ordinal not in range(128)" if module else f"encoding problem: {cs}", self.line - 1 if module else csline)
        # the first line CPython cannot read: not UTF-8 (without a declaration), or a NUL byte
        i = 3 if bom else 0
        line = self.line
        while i < len(src) and not module:
            e = src.find("\n", i)
            if e < 0:
                e = len(src) - 1
            k = i
            while k <= e and not self.declared and kind == 0:
                v = ord(src[k])
                if v == 0:
                    break
                n = 1 if v < 128 else utf8len(src, k)
                if n <= 0:
                    self.cut = f"Non-UTF-8 code starting with '\\x{v:02x}' in file {diagnostics.SRC} on line {line}, but no encoding declared; see https://peps.python.org/pep-0263/ for details"
                    break
                k += n
            if self.cut == "" and src.find(chr(0), i, e + 1) >= 0:
                self.cut = "source code cannot contain null bytes"
            if self.cut != "":
                self.src = src[:i]
                self.cutline = line
                break
            i = e + 1
            line += 1
        return self.run()

    def run(self) -> list[Tok]:
        src = self.src
        n = len(src)
        indents = [0]
        opens: list[str] = []  # the brackets open, and their lines
        openl: list[int] = []
        if src.startswith(chr(239) + chr(187) + chr(191)):  # a UTF-8 byte order mark
            self.i = 3
        bol = True
        while self.i < n:
            c = src[self.i]
            if bol and len(opens) == 0:
                col = 0
                while self.i < n and (src[self.i] == " " or src[self.i] == "\f"):
                    col = col + 1 if src[self.i] == " " else 0  # (a form feed restarts the count, as in CPython)
                    self.i += 1
                if self.i >= n:
                    break
                c = src[self.i]
                j = self.i
                while j < n and (src[j] == " " or src[j] == "\t"):
                    j += 1
                if c == "\t" and (j >= n or src[j] == "\n" or src[j] == "#" or src[j] == "\r"):
                    c = src[j] if j < n else "\n"  # a blank or comment line may be indented with tabs
                if c == "\n" or c == "#" or c == "\r":
                    while self.i < n and src[self.i] != "\n":
                        self.i += 1
                    self.i += 1
                    self.line += 1
                    continue
                if c == "\t":
                    self.stop("tabs are not supported for indentation", self.line)
                    break
                bol = False
                if col > indents[-1]:
                    if len(indents) == 100:
                        self.stop("too many levels of indentation", self.line)  # (CPython's MAXINDENT)
                        break
                    indents.append(col)
                    self.add("indent", "")
                while col < indents[-1]:
                    indents.pop()
                    self.add("dedent", "")
                if col != indents[-1]:
                    self.stop("unindent does not match any outer indentation level", self.line)
                    break
            elif c == "\n":
                if len(opens) == 0:
                    self.add("nl", "")
                    bol = True
                self.line += 1
                self.i += 1
            elif c == " " or c == "\t" or c == "\r" or c == "\f":
                self.i += 1
            elif c == "#":
                while self.i < n and src[self.i] != "\n":
                    self.i += 1
            elif c == "\\" and (src.startswith("\n", self.i + 1) or self.i + 1 == n):
                self.i += 2
                self.line += 1
                if self.i >= n and len(opens) == 0:
                    self.stop("unexpected EOF while parsing", self.line - 1)
            elif (c >= "0" and c <= "9") or (c == "." and src[self.i + 1 : self.i + 2] >= "0" and src[self.i + 1 : self.i + 2] <= "9"):
                self.number()
            elif c.isalpha() or c == "_" or ord(c) >= 128:
                self.word()
            elif c == '"' or c == "'":
                self.string("")
            else:
                self.op()
                k = self.toks[-1].kind
                if (k == "(" or k == "[" or k == "{") and len(opens) == 200:
                    self.bad("too many nested parentheses", self.line)  # (CPython's MAXLEVEL)
                elif k == "(" or k == "[" or k == "{":
                    opens.append(k)
                    openl.append(self.line)
                elif (k == ")" or k == "]" or k == "}") and len(opens) == 0:
                    self.bad(f"unmatched '{k}'", self.line)
                elif k == ")" or k == "]" or k == "}":
                    o = opens.pop()
                    ol = openl.pop()
                    if "([{".find(o) != ")]}".find(k):
                        self.bad(f"closing parenthesis '{k}' does not match opening parenthesis '{o}'" + (f" on line {ol % LINES}" if ol != self.line else ""), self.line)
        ended = len(self.toks) > 0 and (self.toks[-1].kind == "error" or self.toks[-1].kind == "stop")
        if self.cut != "" and not ended:
            self.bad(self.cut, self.cutline)
        elif len(opens) > 0 and not ended:
            self.stop(f"'{opens[-1]}' was never closed", openl[-1])
        if not bol:
            self.add("nl", "")
        while len(indents) > 1:
            indents.pop()
            self.add("dedent", "")
        self.add("eof", "")
        return self.toks

    def number(self) -> None:
        # a number literal, scanned as CPython's tokenizer does (its error messages included)
        src = self.src
        j = self.i
        pfx = src[j : j + 2].lower()
        if pfx == "0x" or pfx == "0o" or pfx == "0b":
            base = 16 if pfx == "0x" else (8 if pfx == "0o" else 2)
            kind = "hexadecimal" if base == 16 else ("octal" if base == 8 else "binary")
            ds = "0123456789abcdefABCDEF" if base == 16 else "01234567"[:base]
            j += 2
            while True:
                # digits, with single underscores between them (and after the prefix)
                if src[j : j + 1] == "_":
                    j += 1
                if j >= len(src) or ds.find(src[j]) < 0:
                    c = src[j : j + 1]
                    self.bad(f"invalid digit '{c}' in {kind} literal" if c >= "0" and c <= "9" else f"invalid {kind} literal", self.line)
                    return
                while j < len(src) and ds.find(src[j]) >= 0:
                    j += 1
                if src[j : j + 1] != "_":
                    break
            if src[j : j + 1] >= "0" and src[j : j + 1] <= "9":
                self.bad(f"invalid digit '{src[j]}' in {kind} literal", self.line)
                return
            if not self.end_of_number(j, kind):
                return
            h = src[self.i + 2 : j].replace("_", "").lstrip("0")
            # significant bits, without converting a number that may not fit
            bits = 0
            if h != "":
                d0 = int(h[0], 16)
                while d0 > 0:
                    bits += 1
                    d0 = d0 >> 1
                bits += (len(h) - 1) * (4 if base == 16 else (3 if base == 8 else 1))
            if bits > 64 or (bits == 64 and (h[1:].strip("0") != "" or int(h[0], 16) & (int(h[0], 16) - 1) != 0)):
                # Gen rejects the literal where it compiles it: "integer literal does not fit in 64 bits"
                self.add("int", "99999999999999999999")
                self.i = j
                return
            # 2**63 is valid only negated; Gen checks that, as for decimal literals
            self.add("int", "9223372036854775808" if bits == 64 else str(int("0" + h, base)))
            self.i = j
            return
        isf = src[j] == "."
        if src[j] == "0":
            # 0, 00 or 0_0; other digits after a leading zero only in a float or imaginary literal
            j += 1
            while src[j : j + 1] == "0" or src[j : j + 1] == "_":
                if src[j] == "_" and not (src[j + 1 : j + 2] >= "0" and src[j + 1 : j + 2] <= "9"):
                    self.bad("invalid decimal literal", self.line)
                    return
                j += 1
            k = j
            j = self.decimals(j)
            if j < 0:
                return
            c = src[j : j + 1]
            if j > k and c != "." and c != "e" and c != "E" and c != "j" and c != "J":
                self.bad("leading zeros in decimal integer literals are not permitted; use an 0o prefix for octal integers", self.line)
                return
        elif not isf:
            j = self.decimals(j)
            if j < 0:
                return
        if src[j : j + 1] == ".":
            isf = True
            j += 1
            if src[j : j + 1] >= "0" and src[j : j + 1] <= "9":
                j = self.decimals(j)
                if j < 0:
                    return
        if src[j : j + 1] == "e" or src[j : j + 1] == "E":
            k = j + 1
            if src[k : k + 1] == "+" or src[k : k + 1] == "-":
                k += 1
                if not (src[k : k + 1] >= "0" and src[k : k + 1] <= "9"):
                    self.bad("invalid decimal literal", self.line)
                    return
            if src[k : k + 1] >= "0" and src[k : k + 1] <= "9":
                isf = True
                j = self.decimals(k)
                if j < 0:
                    return
            elif not self.end_of_number(j, "decimal"):
                return
            else:
                # 1else: the literal ends before the e
                self.add("float" if isf else "int", src[self.i : j].replace("_", ""))
                self.i = j
                return
        if src[j : j + 1] == "j" or src[j : j + 1] == "J":
            if self.end_of_number(j + 1, "imaginary"):
                self.add("complex", src[self.i : j].replace("_", "") + "j")
                self.i = j + 1
            return
        if self.end_of_number(j, "decimal"):
            self.add("float" if isf else "int", src[self.i : j].replace("_", ""))
            self.i = j

    def decimals(self, j: int) -> int:
        # the end of the digits from j, with single underscores between them (-1 after an error)
        src = self.src
        while True:
            while j < len(src) and src[j] >= "0" and src[j] <= "9":
                j += 1
            if src[j : j + 1] != "_":
                return j
            j += 1
            if not (src[j : j + 1] >= "0" and src[j : j + 1] <= "9"):
                self.bad("invalid decimal literal", self.line)
                return -1

    def end_of_number(self, j: int, kind: str) -> bool:
        # what may follow a number literal (CPython's verify_end_of_number): the keyword and, else,
        # for, not or or, or if, in or is at the start of a name (with a SyntaxWarning, which
        # Pystachy does not print), but no other letter, digit or "_"
        src = self.src
        for w in ["and", "else", "for", "not", "or", "if", "in", "is"]:
            c = src[j + len(w) : j + len(w) + 1]
            if src.startswith(w, j) and (len(w) == 2 and w != "or" or not (c != "" and (c.isalnum() or c == "_" or ord(c) >= 128))):
                return True
        c = src[j : j + 1]
        if c != "" and (c.isalnum() or c == "_") and ord(c) < 128:
            self.bad(f"invalid {kind} literal", self.line)
            return False
        return True

    def word(self) -> None:
        src = self.src
        j = self.i
        while j < len(src) and (src[j].isalnum() or src[j] == "_" or ord(src[j]) >= 128):
            j += 1
        w = src[self.i : j]
        k = 0
        letter = False
        while k < len(w):
            # CPython's error for the first character no identifier may hold; a non-ASCII letter
            # is a Pystachy limitation
            n = 1 if ord(w[k]) < 128 else utf8len(w, k)
            cp = codepoint(w, k) if n > 1 else 0
            if among(cp, NONPRINT):
                self.bad(f"invalid non-printable character U+{cp:04X}", self.line)
                return
            if among(cp, NOTID):
                # ("%c" is the character's UTF-8 natively, where chr() below 256 is one byte, and
                # the character where CPython runs this, where the source's own bytes are Latin-1)
                ch = "%c" % cp
                self.bad(f"invalid character '{ch}' (U+{cp:04X})", self.line)
                return
            if n <= 0:
                self.bad("(unicode error) " + utf8_error(w), self.line)  # (in a file declared UTF-8)
                return
            letter = letter or n != 1
            k += n
        if letter:
            self.stop("non-ASCII identifiers are not supported", self.line)
            return
        self.i = j
        if j < len(src) and (src[j] == '"' or src[j] == "'") and len(w) <= 2:
            p = w.lower()
            if p == "f" or p == "r" or p == "u" or p == "fr" or p == "rf":
                self.string(p)
                return
            if p == "b" or p == "br" or p == "rb":
                self.string(p)
                return
        self.add(w if w in KEYWORDS else "id", w)

    def string(self, prefix: str) -> None:
        src = self.src
        q = src[self.i]
        line = self.line
        triple = src.startswith(q + q + q, self.i)
        self.i += 3 if triple else 1
        start = self.i
        # f-strings: one entry per open replacement field, the brackets open in its expression,
        # or -1 once its format spec began (a top-level ':'), where quotes are plain text
        fields: list[int] = []
        while True:
            if self.i >= len(src):
                self.unterminated(prefix, triple, len(fields) > 0, line)
                return
            c = src[self.i]
            if c == q and (not triple or src.startswith(q + q + q, self.i)):
                if len(fields) > 0 and fields[-1] >= 0 and not triple and self.reuses_quote(q):
                    self.stop("f-string: reusing the string's quote inside a replacement field (PEP 701) is not supported; use the other quote", line)
                    return
                break
            if "f" in prefix and (len(fields) == 0 or fields[-1] < 0):
                # literal text, or a format spec: {{ and }} are braces, { opens a field, } closes one
                if c == "{" or c == "}":
                    if len(fields) == 0 and src[self.i + 1 : self.i + 2] == c:
                        self.i += 2
                        continue
                    if c == "{" and len(fields) == 3:
                        self.stop("f-string: expressions nested too deeply", self.line)
                        return
                    if c == "{":
                        fields.append(0)
                    elif len(fields) > 0:
                        fields.pop()
            elif "f" in prefix:
                if c == "'" or c == '"':
                    # a string inside a field ends at its own quote
                    j = src.find(c, self.i + 1)
                    if j > 0 and src.find("\n", self.i, j) < 0:
                        self.i = j + 1
                        continue
                elif c == "(" or c == "[" or c == "{":
                    fields[-1] += 1
                elif c == ")" or c == "]":
                    fields[-1] = max(fields[-1] - 1, 0)
                elif c == "}" and fields[-1] > 0:
                    fields[-1] -= 1
                elif c == "}":
                    fields.pop()
                elif c == ":" and fields[-1] == 0:
                    fields[-1] = -1
                elif c == "#":
                    # a comment, to the end of the line, after which the field goes on
                    j = src.find("\n", self.i)
                    if j < 0:
                        self.stop("'{' was never closed", line)
                        return
                    self.i = j
                    continue
            if c == "\n":
                # (a field's expression may go on over lines, in any f-string)
                if not triple and len(fields) > 0 and fields[-1] < 0:
                    self.stop("f-string: newlines are not allowed in format specifiers for single quoted f-strings", self.line)
                    return
                if not triple and len(fields) == 0:
                    self.unterminated(prefix, triple, False, line)
                    return
                self.line += 1
            if c == "\\":
                # an escaped character never ends the literal, even in a raw string
                if src[self.i + 1 : self.i + 2] == "\n":
                    self.line += 1
                self.i += 2
                continue
            self.i += 1
        text = src[start : self.i]
        self.i += 3 if triple else 1
        if self.declared and "b" not in prefix and utf8_error(text) != "":
            # (only a file declared UTF-8 is not checked as CPython reads it)
            self.stop("(unicode error) " + utf8_error(text), line)
        elif "f" in prefix:
            # decoded later, piece by piece, so escapes never turn into replacement fields
            self.toks.append(Tok("rfstr" if "r" in prefix else "fstr", text, line))
        else:
            # (decoded where the parser reaches it, as CPython does)
            self.toks.append(Tok("bytes" if "b" in prefix else "str", text, line))
            self.toks[-1].esc = "r" not in prefix

    def unterminated(self, prefix: str, triple: bool, field: bool, line: int) -> None:
        # CPython's error for a string literal that the line (or the file) ends in
        at = self.line % LINES
        if self.i >= len(self.src) and self.src.endswith("\n"):
            at -= 1
        kind = ("triple-quoted " if triple else "") + ("f-string" if "f" in prefix else "string")
        if field or "f" in prefix:
            self.stop("'{' was never closed" if field else f"unterminated {kind} literal (detected at line {at})", line)
        else:
            self.bad(f"unterminated {kind} literal (detected at line {at})", line)

    def reuses_quote(self, q: str) -> bool:
        # f"{d["k"]}": the quote that would end the f-string inside a field starts a string that
        # closes on this line and is followed by more of the expression (an operator, or a keyword:
        # f"{f"a" if x else ""}"); otherwise the field is unclosed
        src = self.src
        j = src.find(q, self.i + 1)
        if j < 0 or src.find("\n", self.i, j) >= 0:
            return False
        k = j + 1
        while k < len(src) and src[k] == " ":
            k += 1
        return k < len(src) and (src[k] in "])}.,[!:=+*%<>" or (k > j + 1 and src[k].isalpha()))

    def op(self) -> None:
        for o in OPS:
            if self.src.startswith(o, self.i):
                self.add(o, o)
                self.i += len(o)
                return
        c = self.src[self.i]
        if c == "\\":
            self.stop("unexpected character after line continuation character", self.line)
        elif ord(c) < 32 or ord(c) == 127:
            self.bad(f"invalid non-printable character U+{ord(c):04X}", self.line)
        else:
            # ($, ?, `, a lone !): an operator to CPython's tokenizer, and invalid syntax where its
            # parser reaches it (see Parser.peek)
            self.add("?", c)
            self.i += 1


# ---------------------------------------------------------------- parser
