"""Pystachy: a self-hosting compiler for a statically typed subset of Python.

source -> Lexer -> Parser (AST) -> Gen (type check + LLVM IR in one pass) -> LLVM
`pystachy run` JIT-executes the program with lli (ORC); `pystachy build` compiles it AOT
with clang. This file is itself written in the Pystachy subset and compiles itself.
"""
from __future__ import annotations
import sys
import os
import tempfile

SRC = "<input>"
# the files of the program's modules: a node of FILES[k] has line k * LINES + its line in the file
LINES = 10000000
FILES: list[str] = []
# how deeply source may nest: CPython's tokenizer allows 200 open brackets and 99 indentation
# levels; past MAXNEST levels of nested expressions or elif branches (a ** or lambda counts twice)
# Pystachy rejects the program, below the depths where CPython's parser and compiler give up, and
# so that neither compiler runs out of stack
MAXNEST = 5000
TOODEEP = f"source too complex: nested more than {MAXNEST} levels deep"
# CPython's parser gives up past 6,000 levels of its rules (MemoryError), some 34 of them below a
# statement's expression: Parser.deeper() counts its own levels and the rules CPython goes through
# besides (Parser.extra), as measured, to stop where CPython does or a few levels before
CPYSTACK = 5960
MODDUNDERS = "__file__ __doc__ __spec__ __loader__ __package__ __builtins__"  # (which CPython's modules have)


def shown(s: str) -> str:
    # a name as Python spells it: the "$" of a qualified name (heapq$heappush) between two
    # identifier characters is the "." of a module attribute; the main program's names are
    # its own (__main__$len, a def that shadows a builtin, is len)
    s = s.replace("__main__$", "")
    out: list[str] = []
    for i in range(len(s)):
        c = s[i]
        if c == "$" and i > 0 and i + 1 < len(s) and (s[i - 1].isalnum() or s[i - 1] == "_") and (s[i + 1].isalnum() or s[i + 1] == "_"):
            c = "."
        out.append(c)
    return "".join(out)


def where(line: int) -> str:
    # file:line of a node's line
    if line >= LINES:
        return f"{FILES[line // LINES]}:{line % LINES}"
    return f"{SRC}:{line}"


def fail(msg: str, line: int) -> None:
    print(f"{where(line)}: error: {shown(msg)}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- lexer
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
                    self.cut = f"Non-UTF-8 code starting with '\\x{v:02x}' in file {SRC} on line {line}, but no encoding declared; see https://peps.python.org/pep-0263/ for details"
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
                # (chr() is the same bytes natively, and the character where CPython runs this)
                self.bad(f"invalid character '{chr(cp) if cp >= 256 else w[k : k + n]}' (U+{cp:04X})", self.line)
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
class Node:
    def __init__(self, kind: str, s: str, line: int):
        self.kind = kind
        self.s = s
        self.line = line
        self.kids: list[Node] = []
        self.chk = False  # a variable read that may find the variable unassigned
        # a read of a module's attribute through a name that an import in a try statement binds,
        # which an exception may have left unbound: "<module> <name> <L (a local) or G>", else ""
        self.mchk = ""
        self.depth = 1  # levels of nodes from this one down, as mk counted them


def mk(kind: str, s: str, line: int, kids: list[Node]) -> Node:
    n = Node(kind, s, line)
    n.kids = kids
    for k in kids:
        if k.depth >= n.depth:
            n.depth = k.depth + 1
    d = n
    while n.depth > MAXNEST and len(d.kids) > 0:
        # a chain such as a + b + ..., which the parser builds without recursing: the error is on the
        # line of its deepest node
        for k in d.kids:
            if k.depth == d.depth - 1:
                d = k
                break
    if n.depth > MAXNEST:
        fail(TOODEEP, d.line)
    return n


def mentions(n: Node, names: list[str]) -> bool:
    # does expression n use one of names
    if n.kind == "name" and n.s in names:
        return True
    for k in n.kids:
        if mentions(k, names):
            return True
    return False


def flat_del(n: Node, out: list[Node]) -> None:
    if n.kind == "tuple" or n.kind == "list":
        for k in n.kids:
            flat_del(k, out)
    else:
        out.append(n)


def as_target(n: Node) -> Node:
    # [a, b] = ... and for [a, b] in ...: a list display as a target unpacks like a tuple
    if n.kind == "list" or n.kind == "tuple":
        n.kind = "tuple"
        for k in n.kids:
            as_target(k)
    return n


def dc_args(d: Node) -> str:
    # the arguments of a @dataclass(...) decorator d: "kw" for kw_only=True, "" for none (or
    # kw_only=False), "!" and the error for any other
    r = ""
    if len(d.kids) > 0 and d.kids[0].kind != "call":
        return "!@dataclass(...) with arguments is not supported"
    for a in d.kids[0].kids[1:] if len(d.kids) > 0 else []:
        if a.kind != "kw" or a.s != "kw_only":
            return "!@dataclass(" + (a.s + "=..." if a.kind == "kw" else "...") + ") is not supported: of its arguments, only kw_only= is"
        if a.kids[0].kind != "True" and a.kids[0].kind != "False":
            return "!@dataclass(kw_only=...) needs True or False"
        r = "kw" if a.kids[0].kind == "True" else ""
    return r


def name_targets(t: Node) -> bool:
    # whether the targets of an assignment are only names, which no store to another can change
    if t.kind == "tuple":
        for k in t.kids:
            if not name_targets(k):
                return False
        return True
    return t.kind == "name"


# CPython's name for an expression in its "cannot assign to" errors (_PyPegen_get_expr_name)
EXPRNAMES: dict[str, str] = {
    "attr": "attribute", "index": "subscript", "slice": "subscript", "starred": "starred", "name": "name", "list": "list",
    "tuple": "tuple", "lambda": "lambda", "call": "function call", "binop": "expression", "unary": "expression",
    "boolop": "expression", "yield": "yield expression", "await": "await expression", "setcomp": "set comprehension",
    "dictcomp": "dict comprehension", "dict": "dict literal", "dstar": "dict literal", "set": "set display",
    "fstr": "f-string expression", "str": "literal", "int": "literal", "float": "literal", "complex": "literal",
    "bytes": "literal", "None": "None", "True": "True", "False": "False", "ellipsis": "ellipsis", "cmp": "comparison",
    "ifexp": "conditional expression", "walrus": "named expression",
}


def expr_name(n: Node) -> str:
    if n.kind == "listcomp" or n.kind == "nestedcomp" or n.kind == "asynccomp":
        return "generator expression" if n.s == "gen" else "list comprehension"
    return EXPRNAMES.get(n.kind, "expression")


def start(n: Node) -> int:
    # the line expression n starts on (an operator, call, attribute or subscript node has its
    # operator's line)
    k = n.kind
    if k == "binop" or k == "boolop" or k == "cmp" or k == "call" or k == "attr" or k == "index" or k == "slice":
        return start(n.kids[0])
    if k == "ifexp":
        return start(n.kids[1])
    return n.line


def bad_target(n: Node, delete: bool, out: list[Node]) -> None:
    # the first part of target n that cannot be assigned to (or deleted), as CPython's parser finds it
    k = n.kind
    if len(out) > 0:
        return
    if k == "tuple" or k == "list":
        for x in n.kids:
            bad_target(x, delete, out)
    elif k == "starred" and not delete:
        bad_target(n.kids[0], delete, out)
    elif k != "name" and k != "attr" and k != "index" and k != "slice":
        out.append(n)


STARTS: dict[str, bool] = {}
for _k in "id int float str fstr rfstr bytes complex ... ( [ { - + ~ not None True False lambda yield await".split():
    STARTS[_k] = True
CMPOPS: dict[str, bool] = {"<": True, ">": True, "==": True, ">=": True, "<=": True, "!=": True, "in": True}
AUGOPS: dict[str, bool] = {}
for _k in "+= -= *= /= //= %= **= &= |= ^= <<= >>= @=".split():
    AUGOPS[_k] = True
BINOPS: list[list[str]] = [["|"], ["^"], ["&"], ["<<", ">>"], ["+", "-"], ["*", "/", "//", "%", "@"]]


class Parser:
    def __init__(self, toks: list[Tok]):
        self.toks = toks
        self.p = 0
        self.early = True  # only a docstring and from __future__ imports so far
        self.loops = 0  # loops around the statement being parsed, in its function or class
        self.infn = False  # inside a def
        self.nest = 0  # the parser's own recursion: nested expressions and elif branches
        self.extra = 0  # CPython's parser's levels other than those: in brackets, blocks and operators
        self.xstar = -1  # the loops around the except* block the statement is in (-1: none)
        self.errs: list[str] = ["", "", ""]  # see later()
        self.at: list[int] = [0, 0, 0]
        # an f-string field's parser: the parsers it is in, and where each is, whose tokens follow
        self.outer: list[list[Tok]] = []
        self.outerp: list[int] = []
        self.orp = -1  # the tokens of the disjunction that an expression ended with (see comma())
        self.ore = -1
        self.orn = mk("omit", "", 0, [])
        self.tparams: dict[int, str] = {}  # the type parameters of the generic defs and classes, by line
        # what a generic def or class or a type statement (by line) evaluates in a scope of its own
        # that the parser drops: its type parameters' bounds and defaults, a type alias's value, a
        # generic def's annotations that name its type parameters (each in an "annotation" node)
        self.tpx: dict[int, list[Node]] = {}

    def peek(self) -> str:
        t = self.toks[self.p]
        if t.kind == "error" or t.kind == "stop":
            fail(t.text, t.line)  # (the tokenizer's error, see Lexer.bad)
        if t.kind == "?":
            self.fail("invalid syntax", t.line)
        return t.kind

    def ahead(self) -> str:
        return self.toks[self.p + 1].kind

    def line(self) -> int:
        return self.toks[self.p].line

    def eat(self, k: str) -> bool:
        if self.peek() == k:
            self.p += 1
            return True
        return False

    def expect(self, k: str) -> Tok:
        t = self.toks[self.p]
        if self.peek() != k:
            if k == ":" and t.kind == "nl":
                self.fail("expected ':'", t.line)
            if k == "indent":
                self.fail("expected an indented block", t.line)
            if (k == ")" or k == "]" or k == "}") and self.ore == self.p:
                self.comma()
            self.invalid(t.line)  # (CPython's parser says only that, where its grammar forces no token)
        self.p += 1
        return t

    def comma(self) -> None:
        # in brackets, an expression right after the disjunction an expression ended with: CPython
        # says that a comma may be missing (not after a name that a string follows, nor after a
        # soft keyword), and after print or exec that its call's parentheses are
        a = self.toks[self.orp]
        e = self.orn
        k = self.peek()
        if k == "-" or k == "+" or k == "~" or k == "not":
            k = self.ahead()
        if (k not in STARTS and k != "id") or k == "yield":
            return
        if e.kind == "name" and (e.s == "print" or e.s == "exec"):
            self.fail(f"Missing parentheses in call to '{e.s}'. Did you mean {e.s}(...)?", e.line)
        b = self.toks[self.orp + 1].kind
        if a.kind == "id" and (b == "str" or b == "fstr" or b == "rfstr" or b == "bytes" or a.text == "match" or a.text == "case" or a.text == "_" or a.text == "type"):
            return
        self.fail("invalid syntax. Perhaps you forgot a comma?", start(e))

    def colon(self) -> None:
        # a ':' that CPython's grammar forces (after a def's signature, try, else and finally)
        if self.peek() != ":":
            self.fail("expected ':'", self.line())
        self.p += 1

    def invalid(self, line: int) -> None:
        self.fail("invalid syntax", line)

    def fail(self, msg: str, line: int) -> None:
        # an error of CPython's parser: CPython then tokenizes the rest of the file, and an error
        # its tokenizer raises there replaces it ("error" tokens); a bracket never closed does
        # only if it opened on a line before the one the parser got to
        cur = self.toks[min(self.p, len(self.toks) - 1)].line
        for k in range(len(self.outer) + 1):
            toks = self.toks if k == 0 else self.outer[-k]
            for t in toks[self.p if k == 0 else self.outerp[-k] :]:
                if t.kind == "error" or (t.kind == "stop" and t.text.endswith("was never closed") and t.line < cur):
                    fail(t.text, t.line)
        fail(msg, line)

    def assignable(self, t: Node) -> Node:
        # a for loop's, comprehension's or with statement's target
        bad: list[Node] = []
        bad_target(t, False, bad)
        if len(bad) > 0:
            self.fail(f"cannot assign to {expr_name(bad[0])}", start(bad[0]))
        return t

    def later(self, cat: int, msg: str, line: int) -> None:
        # an error CPython reports only once it has parsed the whole file: its symbol table's (cat
        # 0) or its compiler's (cat 2); the earliest of each is kept (on one line, the first found)
        if self.errs[cat] == "" or line < self.at[cat]:
            self.errs[cat] = msg
            self.at[cat] = line

    def no_debug(self, name: str, line: int) -> None:
        # CPython's compiler: nothing may bind __debug__ (an assignment's targets: Symtable.store())
        if name == "__debug__":
            self.later(2, "cannot assign to __debug__", line)

    def no_star(self, e: Node) -> Node:
        # a value that is a lone *x (x = *a, return *a): an error of CPython's compiler, which
        # Symtable reports in its order (s "here")
        if e.kind == "starred":
            e.s = "here"
        return e

    def docstring(self) -> bool:
        # does the file start with a docstring: string literals (no f-string), maybe in
        # parentheses, alone in a statement
        j = 0
        d = 0
        while self.toks[j].kind == "(":
            d += 1
            j += 1
        if self.toks[j].kind != "str":
            return False
        while self.toks[j].kind == "str":
            j += 1
        while d > 0 and self.toks[j].kind == ")":
            d -= 1
            j += 1
        return d == 0 and (self.toks[j].kind == "nl" or self.toks[j].kind == ";")

    # ---- statements
    def module(self) -> Node:
        body: list[Node] = []
        doc = self.docstring()
        while self.peek() != "eof":
            if not self.eat("nl"):
                self.stmt(body)
        st = Symtable(self.errs, self.at)
        st.tparams = self.tparams
        st.tpx = self.tpx
        st.check(body, doc)
        return mk("block", "", 1, body)

    def scope(self, fn: bool) -> Node:
        # the body of a def (fn) or class: no loop around it
        loops = self.loops
        infn = self.infn
        xstar = self.xstar
        self.loops = 0
        self.infn = fn
        self.xstar = -1
        b = self.block()
        self.loops = loops
        self.infn = infn
        self.xstar = xstar
        return b

    def block(self) -> Node:
        line = self.line()
        body: list[Node] = []
        self.extra += 7  # (6 or 7 in CPython's parser)
        if self.eat("nl"):
            self.expect("indent")
            while not self.eat("dedent"):
                if not self.eat("nl"):
                    self.stmt(body)
        else:
            self.simple(body)
        self.extra -= 7
        return mk("block", "", line, body)

    def stmt(self, out: list[Node]) -> None:
        k = self.peek()
        line = self.line()
        if k != "from" and k != "import" and not (self.p == 0 and self.docstring()):
            self.early = False  # from __future__ imports may follow only a docstring
        if k == "def":
            out.append(self.funcdef())
        elif k == "class":
            # class C(bases): a "subclass" node (the class, then the bases), which code generation
            # rejects where it needs the class (class C(object): see Loader.deftime)
            self.p += 1
            name = self.expect("id").text
            bases: list[Node] = []
            tps: list[str] = []
            if self.peek() == "[":
                self.typeparams(tps, line)
                bases.append(mk("typeparams", " ".join(tps), line, []))  # class C[T]: a generic class
                self.tparams[line] = " ".join(tps)
            if self.eat("("):
                args = mk("call", "", line, [])
                self.args(args, line, True)
                bases.extend(args.kids)
                for b in args.kids if len(tps) > 0 else []:
                    self.scoped(b, "the definition of a generic")
            self.expect(":")
            self.no_debug(name, line)
            c = mk("class", name, line, [self.scope(False)])
            if len(bases) == 0:
                out.append(c)
            else:
                out.append(mk("subclass", name, line, [c] + bases))
        elif k == "if":
            out.append(self.ifstmt())
        elif k == "while":
            self.p += 1
            c = self.named()
            self.expect(":")
            self.loops += 1
            out.append(mk("while", "", line, [c, self.block()]))
            self.loops -= 1
        elif k == "for":
            self.p += 1
            t = self.targets()
            self.expect("in")
            it = self.no_star(self.exprlist())
            self.expect(":")
            self.loops += 1
            out.append(mk("for", "", line, [t, it, self.block()]))
            self.loops -= 1
        elif k == "@":
            # a decorator: s is its dotted name, a decorator with arguments (or that is no dotted
            # name: s has a "?") keeps its expression as its kid
            self.p += 1
            e = self.named()
            self.expect("nl")
            k = self.peek()
            if k != "def" and k != "class" and k != "@" and k != "async" and k != "indent":
                self.invalid(self.line())
            if k == "async" and self.ahead() != "def":
                self.invalid(self.toks[self.p + 1].line)
            self.stmt(out)
            d = out[-1]
            if d.kind == "subclass":
                d = d.kids[0]
            fn = e.kids[0] if e.kind == "call" else e
            name = ""
            while fn.kind == "attr":
                name = "." + fn.s + name
                fn = fn.kids[0]
            name = (fn.s if fn.kind == "name" else "?") + name
            d.kids.append(mk("deco", name, line, [e] if e.kind == "call" or "?" in name else []))
        elif k == "with":
            # with open(p) as f, ...: kids are the items (expression [, target]) and the block
            self.p += 1
            items: list[Node] = []
            paren = self.peek() == "(" and self.with_parens()
            if paren:
                self.p += 1
            while not (paren and self.peek() == ")"):
                it = mk("withitem", "", line, [self.test()])
                if self.eat("as"):
                    it.kids.append(as_target(self.assignable(self.item())))
                items.append(it)
                if not self.eat(","):
                    break
            if paren:
                self.expect(")")
            self.expect(":")
            items.append(self.block())
            out.append(mk("with", "", line, items))
        elif k == "try":
            # kids: the body, one "except" node (s: the name bound, kids: type or omit, block) per
            # handler, then the else and finally blocks (blocks with s "else" and "finally"); s is
            # "*" if its handlers are except* clauses
            self.p += 1
            self.colon()
            kids = [self.block()]
            kind = ""  # except or except*
            bare = 0  # the line of an except without a type, which must be the last
            while self.peek() == "except":
                hl = self.line()
                self.p += 1
                star = self.eat("*")
                if kind != "" and kind != ("except*" if star else "except"):
                    self.fail("cannot have both 'except' and 'except*' on the same 'try'", hl)
                kind = "except*" if star else "except"
                if bare > 0:
                    self.later(2, "default 'except:' must be last", bare)
                typ = mk("omit", "", hl, [])
                name = ""
                if self.peek() != ":":
                    typ = self.test()
                    if self.peek() == ",":
                        self.fail("multiple exception types must be parenthesized", start(typ))
                    if self.eat("as"):
                        name = self.expect("id").text
                        self.no_debug(name, hl)
                        if self.peek() != ":":
                            self.invalid(self.line())
                elif star:
                    self.fail("expected one or more exception types", self.line())
                else:
                    bare = hl
                self.expect(":")
                xstar = self.xstar
                if star:
                    self.xstar = self.loops
                kids.append(mk("except", name, hl, [typ, self.block()]))
                self.xstar = xstar
            if len(kids) == 1 and self.peek() != "finally":
                self.fail("expected 'except' or 'finally' block", self.next_line())
            for w in ["else", "finally"]:
                if self.eat(w):
                    self.colon()
                    b = self.block()
                    b.s = w
                    kids.append(b)
            if self.peek() == "except" or self.peek() == "else" or self.peek() == "finally":
                self.invalid(self.line())  # (a clause out of order)
            out.append(mk("try", "*" if kind == "except*" else "", line, kids))
        elif k == "async":
            # async def, async with, async for: kept as an "async" node that code generation rejects
            self.p += 1
            if self.peek() != "def" and self.peek() != "with" and self.peek() != "for":
                self.invalid(self.line())
            inner: list[Node] = []
            self.stmt(inner)
            if inner[0].kind == "def":
                inner[0].kids.append(mk("deco", "async", line, []))
                out.append(inner[0])
            else:
                out.append(mk("async", "", line, inner))
        elif k == "id" and self.toks[self.p].text == "match" and self.soft_match():
            # match subject: case pattern [if guard]: ... -- kept as a "match" node: the subject, then
            # per case a "pattern" node (s: the names the pattern's captures bind; kids: the guard)
            # and the block. A pattern is skipped, not checked.
            self.p += 1
            n = mk("match", "", line, [self.exprlist(True)])
            self.expect(":")
            self.expect("nl")
            self.expect("indent")
            while not self.eat("dedent"):
                if self.eat("nl"):
                    continue
                if self.toks[self.p].text != "case":
                    self.fail("expected 'case'", self.line())
                pat = mk("pattern", "", self.line(), [])
                caps: list[str] = []
                self.p += 1
                depth = 0
                while not (depth == 0 and (self.peek() == ":" or self.peek() == "if")):
                    tk = self.toks[self.p]
                    if tk.kind == "(" or tk.kind == "[" or tk.kind == "{":
                        depth += 1
                    elif tk.kind == ")" or tk.kind == "]" or tk.kind == "}":
                        depth -= 1
                    elif tk.kind == "eof":
                        self.fail("expected ':'", tk.line)
                    elif tk.kind == "id" and tk.text != "_" and self.toks[self.p - 1].kind != "." and self.ahead() != "(" and self.ahead() != "." and self.ahead() != "=":
                        caps.append(tk.text)  # (not a class, a dotted value or a keyword of a class pattern)
                    self.p += 1
                if self.eat("if"):
                    pat.kids.append(self.named())
                self.expect(":")
                pat.s = " ".join(caps)
                n.kids.append(pat)
                n.kids.append(self.block())
            out.append(n)
        else:
            self.simple(out)
        if self.peek() == "else" and (k == "for" or k == "while"):
            # for/while ... else: the else block is the loop's last kid, a block with s "else"
            self.p += 1
            self.colon()
            b = self.block()
            b.s = "else"
            out[-1].kids.append(b)

    def soft_match(self) -> bool:
        # is 'match' at the start of a statement the match keyword: the line ends with ':' and the
        # next line starts with case
        j = self.p + 1
        d = 0
        while j < len(self.toks) and self.toks[j].kind != "nl":
            k = self.toks[j].kind
            if k == "(" or k == "[" or k == "{":
                d += 1
            elif k == ")" or k == "]" or k == "}":
                d -= 1
            j += 1
        return j + 2 < len(self.toks) and self.toks[j - 1].kind == ":" and self.toks[j + 1].kind == "indent" and self.toks[j + 2].text == "case" and j > self.p + 2

    def with_parens(self) -> bool:
        # with (a as x, b as y): parenthesized items, told from a parenthesized expression by an
        # 'as' or ',' directly inside the parentheses and a ':' right after them
        d = 0
        hit = False
        j = self.p
        while j < len(self.toks):
            k = self.toks[j].kind
            if k == "(" or k == "[" or k == "{":
                d += 1
            elif k == ")" or k == "]" or k == "}":
                d -= 1
                if d == 0:
                    return hit and self.toks[j + 1].kind == ":"
            elif d == 1 and (k == "as" or k == ","):
                hit = True
            elif k == "nl" or k == "eof":
                return False
            j += 1
        return False

    def ifstmt(self) -> Node:
        line = self.line()
        self.p += 1
        c = self.named()
        self.expect(":")
        n = mk("if", "", line, [c, self.block(), mk("block", "", line, [])])
        if self.peek() == "elif":
            self.deeper()
            n.kids[2].kids.append(self.ifstmt())
            self.nest -= 1
        elif self.eat("else"):
            self.colon()
            n.kids[2] = self.block()
        return n

    def funcdef(self) -> Node:
        line = self.line()
        self.p += 1
        name = self.expect("id").text
        tps: list[str] = []
        if self.peek() == "[":
            self.typeparams(tps, line)
            self.tparams[line] = " ".join(tps)
        if self.peek() != "(":
            self.fail("expected '('", self.line())
        self.p += 1
        params = self.params(")", line)
        ret = mk("noann", "", line, [])
        if self.eat("->"):
            ret = self.test()
        self.colon()
        self.no_debug(name, line)
        for a in [p.kids[0] for p in params.kids] + [ret] if len(tps) > 0 else []:
            self.scoped(a, "the definition of a generic")
        # def f[T](x: T) -> T: what mentions a type parameter is left unannotated (a template); the
        # annotation is kept as the kid, s the type parameters, for Loader.deftime
        for p in params.kids:
            if mentions(p.kids[0], tps):
                self.dropped(line, mk("annotation", "", line, [p.kids[0]]))
                p.kids[0] = mk("noann", " ".join(tps), line, [p.kids[0]])
        if mentions(ret, tps):
            self.dropped(line, mk("annotation", "", line, [ret]))
            ret = mk("noann", " ".join(tps), line, [ret])
        return mk("def", name, line, [params, ret, self.scope(True)])

    def params(self, end: str, line: int) -> Node:
        # a def's parameters up to ')' or a lambda's up to ':' (without annotations). s is "<number
        # of positional-only parameters>,<index of the first keyword-only one>" (-1: none); *args
        # and **kwargs are "starparam" and "dstarparam" kids. Errors name the line of the token
        # CPython reports.
        params = mk("params", "", line, [])
        seen: dict[str, bool] = {}
        posonly = 0
        kwonly = -1
        slash = False
        star = False  # a * or *args seen
        bare = 0  # the line of a bare * not yet followed by a named parameter
        dstar = False
        while not self.eat(end):
            at = self.line()
            if dstar:
                self.fail("arguments cannot follow var-keyword argument", at)
            if self.eat("/"):
                if slash:
                    self.fail("/ may appear only once", at)
                if kwonly >= 0:
                    self.fail("/ must be ahead of *", at)
                if len(params.kids) == 0:
                    self.fail("at least one argument must precede /" if self.peek() == "," else "invalid syntax", at)
                slash = True
                posonly = len(params.kids)
            elif self.peek() == "*" and (self.ahead() == "," or self.ahead() == end):
                if star:
                    self.fail("* argument may appear only once", at)
                self.p += 1
                star = True
                bare = at
                kwonly = len(params.kids)
            else:
                kind = "param"
                if self.eat("*"):
                    kind = "starparam"
                    if star:
                        self.fail("* argument may appear only once", at)
                    star = True
                elif self.eat("**"):
                    kind = "dstarparam"
                    if bare > 0:
                        self.fail("named arguments must follow bare *", bare if end == ")" else at)
                    dstar = True
                else:
                    bare = 0
                at = self.line()
                pname = self.expect("id").text
                if pname in seen:
                    self.later(0, f"duplicate argument '{pname}' in function definition", at)
                seen[pname] = True
                self.no_debug(pname, at)
                ann = mk("noann", "", line, [])
                dflt = mk("noann", "", line, [])
                if end == ")" and self.eat(":"):
                    ann = self.item() if kind == "starparam" and self.peek() == "*" else self.test()
                if kind != "param" and self.peek() == "=":
                    self.fail(f"var-{'positional' if kind == 'starparam' else 'keyword'} argument cannot have default value", self.line())
                if kind == "param" and self.eat("="):
                    self.extra += 7 if end == ":" else 0  # (a lambda's: 8 levels in CPython's parser)
                    dflt = self.test()
                    self.extra -= 7 if end == ":" else 0
                elif kind == "param" and kwonly < 0 and len(params.kids) > 0 and params.kids[-1].kids[1].kind != "noann":
                    self.fail("parameter without a default follows parameter with a default", at)
                params.kids.append(mk(kind, pname, line, [ann, dflt]))
                if kind == "starparam":
                    kwonly = len(params.kids)
            if not self.eat(","):
                self.expect(end)
                break
        if bare > 0:
            self.fail("named arguments must follow bare *", bare if end == ")" else self.toks[self.p - 1].line)
        params.s = f"{posonly},{kwonly}"
        return params

    def typeparams(self, out: list[str], line: int) -> None:
        # [T, U: bound, *Ts, **P, V = default] after the name of a def, a class or a type alias (on line)
        if self.toks[self.p + 1].kind == "]":
            self.fail("Type parameter list cannot be empty", self.line())
        self.expect("[")
        while not self.eat("]"):
            kind = "TypeVar"
            if self.eat("**"):
                kind = "ParamSpec"
            elif self.eat("*"):
                kind = "TypeVarTuple"
            at = self.line()
            name = self.expect("id").text
            if name in out:
                self.later(0, f"duplicate type parameter '{name}'", at)
            self.no_debug(name, at)
            out.append(name)
            if self.eat(":"):
                b = self.test()
                self.scoped(b, "a TypeVar constraint" if b.kind == "tuple" else "a TypeVar bound")
                self.dropped(line, b)
            if self.eat("="):
                b = self.item()
                self.scoped(b, f"a {kind} default")
                self.dropped(line, b)
            if not self.eat(","):
                self.expect("]")
                break

    def scoped(self, e: Node, what: str) -> None:
        # CPython's symbol table: a type parameter's bound or default, a type alias's value, and a
        # generic's annotations and bases are evaluated in scopes of their own, where yield, await
        # and := cannot stand (except in a lambda, and := in a comprehension neither)
        k = e.kind
        if k == "walrus" or k == "yield" or k == "await":
            self.later(0, f"{'named' if k == 'walrus' else k} expression cannot be used within {what}", e.line)
        if (k == "listcomp" or k == "nestedcomp" or k == "asynccomp" or k == "setcomp" or k == "dictcomp") and has_kind(e, "walrus"):
            where = "within " + what if what.startswith("the") else "in " + (what if what == "a type alias" else "a TypeVar bound")
            self.later(0, f"assignment expression within a comprehension cannot be used {where}", e.line)
        elif k != "lambda":
            for kid in e.kids:
                self.scoped(kid, what)

    def dropped(self, line: int, e: Node) -> None:
        # e, which the parser drops, is compiled by the statement on line (see tpx)
        if line not in self.tpx:
            self.tpx[line] = []
        self.tpx[line].append(e)

    def compnext(self) -> bool:
        # a comprehension's for clause follows
        return self.peek() == "for" or (self.peek() == "async" and self.ahead() == "for")

    def simple(self, out: list[Node]) -> None:
        out.append(self.small())
        while self.eat(";"):
            if self.peek() == "nl":
                break
            out.append(self.small())
        self.expect("nl")

    def small(self) -> Node:
        line = self.line()
        k = self.peek()
        future = k == "from" and self.toks[self.p + 1].text == "__future__"
        if future and not self.early:
            self.later(2, "from __future__ imports must occur at the beginning of the file", line)
        if not future and not (self.p == 0 and self.docstring()):
            self.early = False
        if k == "id" and self.toks[self.p].text == "type" and self.ahead() == "id" and (self.toks[self.p + 2].kind == "=" or self.toks[self.p + 2].kind == "["):
            # type X[T] = value (PEP 695): s is X
            self.p += 1
            name = self.expect("id").text
            tps: list[str] = []
            if self.peek() == "[":
                self.typeparams(tps, line)
            self.expect("=")
            v = self.test()
            self.scoped(v, "a type alias")
            self.dropped(line, v)
            self.no_debug(name, line)
            return mk("typealias", name, line, [])
        if k == "pass" or k == "break" or k == "continue":
            if k != "pass" and self.loops == self.xstar:
                self.later(2, "'break', 'continue' and 'return' cannot appear in an except* block", line)
            elif k != "pass" and self.loops == 0:
                self.later(2, "'break' outside loop" if k == "break" else "'continue' not properly in loop", line)
            self.p += 1
            return mk(k, "", line, [])
        if k == "return":
            if not self.infn:
                self.later(2, "'return' outside function", line)
            elif self.xstar >= 0:
                self.later(2, "'break', 'continue' and 'return' cannot appear in an except* block", line)
            self.p += 1
            if self.peek() == "nl" or self.peek() == ";":
                return mk("return", "", line, [])
            return mk("return", "", line, [self.no_star(self.exprlist())])
        if k == "global":
            self.p += 1
            n = mk("global", "", line, [])
            while True:
                n.kids.append(mk("name", self.expect("id").text, line, []))
                if not self.eat(","):
                    return n
        if k == "import" or k == "from":
            return self.import_(line)
        if k == "assert":
            self.p += 1
            n = mk("assert", "", line, [self.test()])
            if self.eat(","):
                n.kids.append(self.test())
            return n
        if k == "raise":
            self.p += 1
            if self.peek() == "nl" or self.peek() == ";":
                return mk("raise", "", line, [])
            n = mk("raise", "", line, [self.test()])
            if self.peek() == "from":
                self.p += 1
                n.kids.append(self.test())
            return n
        if k == "del":
            # del a, (b, [c]): each name, item or attribute, in order
            self.p += 1
            n = mk("del", "", line, [])
            flat_del(self.item(), n.kids)
            while self.eat(","):
                if self.peek() == "nl" or self.peek() == ";":
                    break
                flat_del(self.item(), n.kids)
            bad: list[Node] = []
            for t in n.kids:
                bad_target(t, True, bad)
            if len(bad) > 0:
                self.fail(f"cannot delete {expr_name(bad[0])}", start(bad[0]))
            for t in n.kids:
                if t.kind == "name" and t.s == "__debug__":
                    self.later(2, "cannot delete __debug__", t.line)
            return n
        if k == "nonlocal":
            self.p += 1
            n = mk("nonlocal", "", line, [])
            while True:
                n.kids.append(mk("name", self.expect("id").text, line, []))
                if not self.eat(","):
                    return n
        p = self.p
        e = self.rhs()
        if e.kind == "name" and e.s == "print" and (self.peek() in STARTS or self.peek() == "id"):
            self.fail("Missing parentheses in call to 'print'. Did you mean print(...)?", line)
        if self.peek() == ":=":
            # CPython's parser also tries the expressions that start a statement as named
            # expressions: x := v where x is no name (nor a starred or yield expression)
            last = e
            if e.kind == "tuple" and not (self.toks[p].kind == "(" and self.close(p) == self.p - 1):
                last = e.kids[-1]
            if last.kind != "starred" and not (last.kind == "yield" and self.toks[p].kind == "yield") and not (last.kind == "name" and self.toks[self.p - 1].kind == "id"):
                self.fail(f"cannot use assignment expressions with {expr_name(last)}", start(last))
        if self.peek() == ":":
            # x: T [= v]; s is "(" for a target in parentheses, which declares no annotated name
            if e.kind == "starred":
                self.invalid(self.line())
            if e.kind == "tuple" or e.kind == "list":
                self.fail(f"only single target (not {e.kind}) can be annotated", start(e))
            if e.kind != "name" and e.kind != "attr" and e.kind != "index" and e.kind != "slice":
                self.fail("illegal target for annotation", start(e))
            self.p += 1
            n = mk("annassign", "(" if self.toks[p].kind == "(" else "", line, [e, self.test()])
            if self.eat("="):
                n.kids.append(self.no_star(self.rhs()))
            return n
        if self.peek() == "=":
            # a = b = v: target i (and the value) starts at token at[i]
            n = mk("assign", "", line, [e])
            at = [p]
            while self.eat("="):
                at.append(self.p)
                n.kids.append(self.rhs())
            self.assign_check(n.kids, at)
            for t in n.kids[:-1]:
                as_target(t)
            return n
        k = self.peek()
        if k in AUGOPS:
            if e.kind != "name" and e.kind != "attr" and e.kind != "index" and e.kind != "slice":
                self.fail(f"'{expr_name(e)}' is an illegal expression for augmented assignment", start(e))
            self.p += 1
            return mk("augassign", k[:-1], line, [e, self.no_star(self.rhs())])
        return mk("expr", "", line, [self.no_star(e)])

    def assign_check(self, ts: list[Node], at: list[int]) -> None:
        # the targets ts[:-1] of an assignment: CPython's parser errors, then its compiler's (which
        # compiles the value first)
        bad: list[Node] = []
        for t in ts[:-1]:
            bad_target(t, False, bad)
        if len(bad) > 0:
            # CPython's parser first tries the first target's last item, then "=", then a bitwise_or
            # that no "=" or ":=" follows, as a misspelt comparison
            eq = at[1] - 1
            cs = self.commas(at[0], eq, ",")
            if ts[0].kind != "tuple":
                cs = []  # (lambda a, b: ...)
            i = cs[-1] + 1 if len(cs) > 0 else at[0]
            last = ts[0].kids[-1] if len(cs) > 0 else ts[0]
            k = self.toks[at[1]].kind
            rhs = k != "yield" and k != "not" and k != "lambda" and k != "*" and not (k == "id" and ts[1].kind == "walrus")
            if len(ts) > 2 and self.bitwise(ts[1], at[1], at[2] - 1):
                rhs = False
            if i < eq and rhs and self.toks[i].kind == "id" and i + 1 == eq:
                self.fail("invalid syntax. Maybe you meant '==' or ':=' instead of '='?", last.line)
            if i < eq and rhs and self.bitwise(last, i, eq) and not self.display(i):
                self.fail(f"cannot assign to {expr_name(last)} here. Maybe you meant '==' instead of '='?", start(last))
            for j in range(len(ts) - 1):
                bad = []
                bad_target(ts[j], False, bad)
                if len(bad) > 0 and bad[0] is ts[j] and self.toks[at[j]].kind == "yield":
                    self.fail("assignment to yield expression not possible", bad[0].line)
                if len(bad) > 0:
                    self.fail(f"cannot assign to {expr_name(bad[0])}", start(bad[0]))
        self.no_star(ts[-1])

    def commas(self, i: int, j: int, k: str) -> list[int]:
        # the tokens of kind k outside brackets among tokens i..j-1
        out: list[int] = []
        d = 0
        while i < j:
            t = self.toks[i].kind
            if t == "(" or t == "[" or t == "{":
                d += 1
            elif t == ")" or t == "]" or t == "}":
                d -= 1
            elif t == k and d == 0:
                out.append(i)
            i += 1
        return out

    def close(self, i: int) -> int:
        # the token that closes the bracket at token i
        d = 0
        while True:
            t = self.toks[i].kind
            if t == "(" or t == "[" or t == "{":
                d += 1
            elif t == ")" or t == "]" or t == "}":
                d -= 1
                if d == 0:
                    return i
            i += 1

    def bitwise(self, e: Node, i: int, j: int) -> bool:
        # is expression e (tokens i..j-1) one bitwise_or of CPython's grammar: no comparison, not,
        # and, or, conditional, lambda, *x, := or yield outside parentheses
        if self.toks[i].kind == "(" and self.close(i) == j - 1:
            return True
        k = e.kind
        return not (k == "cmp" or k == "boolop" or k == "ifexp" or k == "lambda" or k == "walrus" or k == "starred" or k == "tuple" or (k == "unary" and e.s == "not") or k == "yield")

    def display(self, i: int) -> bool:
        # does a list or tuple display, a generator expression, True, None or False start at token i
        k = self.toks[i].kind
        if k == "True" or k == "None" or k == "False":
            return True
        if k != "(" and k != "[":
            return False
        j = self.close(i)
        if len(self.commas(i + 1, j, "for")) > 0:
            return k == "("
        return k == "[" or j == i + 1 or (len(self.commas(i + 1, j, ",")) > 0 and self.toks[i + 1].kind != "yield")

    def next_line(self) -> int:
        # the line CPython reports for the token after a block: at the end of the file, the last line
        j = self.p
        while self.toks[j].kind == "dedent":
            j += 1
        if self.toks[j].kind != "eof":
            return self.toks[self.p].line
        while self.toks[j].kind != "nl":
            j -= 1
        return max(self.toks[j].line, self.toks[-1].line - 1)

    def dotted_name(self) -> str:
        s = self.expect("id").text
        while self.eat("."):
            s = s + "." + self.expect("id").text
        return s

    def import_(self, line: int) -> Node:
        # one alias per bound name: s = the name, kids = [target path, imported module]. The node's
        # own s is "" for import and "from" for from-imports, followed by a relative import's dots
        n = mk("import", "", line, [])
        if self.eat("import"):
            while True:
                path = self.dotted_name()
                name = path[: path.find(".")] if "." in path else path
                tgt = name
                if self.eat("as"):
                    name = self.expect("id").text
                    tgt = path
                n.kids.append(mk("alias", name, line, [mk("str", tgt, line, []), mk("str", path, line, [])]))
                self.no_debug(name, line)
                if not self.eat(","):
                    return n
        self.expect("from")
        n.s = "from"
        while self.peek() == "." or self.peek() == "...":
            n.s += self.toks[self.p].kind
            self.p += 1
        path = self.dotted_name() if self.peek() == "id" or n.s == "from" else ""
        self.expect("import")
        paren = self.eat("(")
        while True:
            x = "*" if self.eat("*") else self.expect("id").text
            name = x
            if x != "*" and self.eat("as"):
                name = self.expect("id").text
            n.kids.append(mk("alias", name, line, [mk("str", path + "." + x if path != "" else x, line, []), mk("str", path, line, [])]))
            self.no_debug(name, line)
            if x == "*" or not self.eat(",") or (paren and self.peek() == ")"):
                break
            if not paren and (self.peek() == "nl" or self.peek() == ";"):
                self.fail("trailing comma not allowed without surrounding parentheses", self.line())
        if paren:
            self.expect(")")
        if path == "collections" and len([a for a in n.kids if a.kids[0].s != "collections.abc"]) == 0:
            # from collections import abc: import collections.abc as abc (a builtin module)
            n.s = ""
            for a in n.kids:
                a.kids[1].s = "collections.abc"
        return n

    # ---- expressions
    def exprlist(self, named: bool = False) -> Node:
        # expressions separated by commas (named: named expressions, as a match statement's subject)
        line = self.line()
        e = self.nitem() if named else self.item()
        if self.peek() != ",":
            return e
        t = mk("tuple", "", line, [e])
        while self.eat(","):
            if self.peek() not in STARTS and self.peek() != "*":
                break
            t.kids.append(self.nitem() if named else self.item())
        return t

    def item(self) -> Node:
        if self.peek() == "*":
            line = self.line()
            self.p += 1
            return mk("starred", "", line, [self.binary(0)])
        return self.test()

    def targets(self) -> Node:
        # the target of a for loop or comprehension (up to 'in', so no comparison)
        line = self.line()
        e = self.item() if self.peek() == "*" else self.binary(0)
        if self.peek() != ",":
            return as_target(self.assignable(e))
        t = mk("tuple", "", line, [e])
        while self.eat(","):
            if self.peek() == "in":
                break
            t.kids.append(self.item() if self.peek() == "*" else self.binary(0))
        return as_target(self.assignable(t))

    def deeper(self) -> None:
        # one more level of the parser's recursion, which the caller undoes
        self.nest += 1
        if self.nest > MAXNEST:
            fail(TOODEEP, self.line())
        if self.nest + self.extra > CPYSTACK:
            fail("source too complex for CPython's parser, whose stack overflows here (MemoryError)", self.line())

    def test(self) -> Node:
        self.deeper()
        e = self.test1()
        self.nest -= 1
        return e

    def test1(self) -> Node:
        # an expression: no x := v outside brackets (CPython's grammar has it only where named()
        # is called), so := after one is "invalid syntax" (see expect())
        line = self.line()
        if self.eat("lambda"):
            # lambda params: body (kids: the parameters, as a def's, then the body; s: "=" if one
            # has a default)
            ps = self.params(":", line)
            self.deeper()  # (a lambda counts as two levels, as a ** does)
            b = self.test()
            self.nest -= 1
            return mk("lambda", "=" if len([x for x in ps.kids if x.kids[1].kind != "noann"]) > 0 else "", line, [ps, b])
        p = self.p
        e = self.or_test()
        self.orp = p
        self.ore = self.p
        self.orn = e
        if self.eat("if"):
            c = self.or_test()
            if self.peek() == ":":
                self.invalid(self.line())
            if self.peek() != "else":
                self.fail("expected 'else' after 'if' expression", start(e))
            self.p += 1
            return mk("ifexp", "", line, [c, e, self.test()])
        return e

    def named(self, arg: bool = False) -> Node:
        # CPython's named_expression, x := v or an expression: a condition, a subscript, an item of
        # a list, set or tuple display, a comprehension's element; or (arg) a call's positional
        # argument, where := after anything but a name is plain invalid syntax
        line = self.line()
        if self.peek() == "id" and self.ahead() == ":=":
            name = self.toks[self.p].text
            self.p += 2
            self.extra += 1
            v = self.test()
            self.extra -= 1
            return mk("walrus", name, line, [v])
        e = self.test()
        if self.peek() == ":=" and arg:
            self.invalid(self.line())
        if self.peek() == ":=":
            self.fail(f"cannot use assignment expressions with {expr_name(e)}", start(e))
        return e

    def nitem(self) -> Node:
        # an item of a list, set or tuple display: *x or a named expression
        if self.peek() == "*":
            return self.item()
        return self.named()

    def rhs(self) -> Node:
        # what may stand after = (and at the start of a statement): a yield expression, or an
        # expression list
        if self.peek() == "yield":
            return self.yield_()
        return self.exprlist()

    def yield_(self) -> Node:
        # yield [values], or yield from x: s is "from"
        line = self.line()
        self.p += 1
        n = mk("yield", "", line, [])
        if self.eat("from"):
            n.s = "from"
            n.kids.append(self.test())
        elif self.peek() in STARTS or self.peek() == "*":
            self.extra += 1  # (a level deeper in CPython's parser than after yield from)
            n.kids.append(self.no_star(self.exprlist()))
            self.extra -= 1
        return n

    def or_test(self) -> Node:
        e = self.and_test()
        while self.peek() == "or":
            line = self.line()
            self.p += 1
            self.extra += 2
            e = mk("boolop", "or", line, [e, self.and_test()])
            self.extra -= 2
        return e

    def and_test(self) -> Node:
        e = self.not_test()
        while self.peek() == "and":
            line = self.line()
            self.p += 1
            self.extra += 2
            e = mk("boolop", "and", line, [e, self.not_test()])
            self.extra -= 2
        return e

    def not_test(self) -> Node:
        line = self.line()
        if self.eat("not"):
            self.deeper()
            e = self.not_test()
            self.nest -= 1
            return mk("unary", "not", line, [e])
        return self.comparison()

    def comparison(self) -> Node:
        line = self.line()
        e = self.binary(0)
        ops: list[str] = []
        kids = [e]
        while True:
            k = self.peek()
            if k in CMPOPS:
                self.p += 1
            elif k == "not" and self.ahead() == "in":
                self.p += 2
                k = "not in"
            elif k == "is":
                self.p += 1
                if self.eat("not"):
                    k = "is not"
            else:
                break
            ops.append(k)
            self.extra += 3
            kids.append(self.binary(0))
            self.extra -= 3
        if len(ops) == 0:
            return e
        return mk("cmp", ",".join(ops), line, kids)

    def binary(self, lvl: int) -> Node:
        if lvl == len(BINOPS):
            return self.unary()
        e = self.binary(lvl + 1)
        while self.peek() in BINOPS[lvl]:
            line = self.line()
            op = self.peek()
            self.p += 1
            e = mk("binop", op, line, [e, self.binary(lvl + 1)])
        return e

    def unary(self) -> Node:
        k = self.peek()
        if k == "-" or k == "+" or k == "~":
            line = self.line()
            self.p += 1
            self.deeper()
            e = self.unary()
            self.nest -= 1
            return mk("unary", k, line, [e])
        e = self.postfix()
        if self.peek() == "**":
            line = self.line()
            self.p += 1
            self.nest += 1  # (two levels: CPython's parser stops at half the depth of other chains)
            self.deeper()
            r = self.unary()
            self.nest -= 2
            return mk("binop", "**", line, [e, r])
        return e

    def postfix(self) -> Node:
        w = 27 if self.peek() == "(" else 28 if self.peek() == "[" or self.peek() == "{" else 0
        self.extra += w  # (the levels of CPython's parser in a bracket, but the one deeper() counts)
        e = self.atom()
        self.extra -= w
        while True:
            line = self.line()
            self.extra += 23
            if self.eat("("):
                c = mk("call", "", line, [e])
                self.args(c, line, False)
                e = c
            elif self.eat("["):
                # x[i], x[lo:hi], x[lo:hi:step] (a step is a fourth kid, which code generation
                # rejects); x[a, b] indexes with a tuple
                items: list[Node] = [self.subscript(line)]
                comma = False
                self.extra += 3
                while self.eat(","):
                    comma = True
                    if self.peek() == "]":
                        break
                    items.append(self.subscript(line))
                self.extra -= 3
                self.expect("]")
                if not comma and items[0].kind == "sliceitem":
                    e = mk("slice", "", line, [e] + items[0].kids)
                else:
                    e = mk("index", "", line, [e, items[0] if not comma else mk("tuple", "", line, items)])
            elif self.eat("."):
                e = mk("attr", self.expect("id").text, line, [e])
            else:
                self.extra -= 23
                return e
            self.extra -= 23

    def args(self, c: Node, line: int, cls: bool) -> None:
        # the arguments of a call (or of a class statement: cls) after '(', appended to c:
        # expressions, "starred" (*x), "kw" (name=x) and "dstar" (**x) nodes
        kws: dict[str, bool] = {}
        keyed = ""  # "kw" after a keyword argument, "dstar" after a ** one
        pos = ""  # a positional argument after those: CPython reports it at the ')'
        gen = 0  # the line of the first generator expression's element
        n = len(c.kids)
        while not self.eat(")"):
            at = self.line()
            w = 4 if len(c.kids) > n or self.peek() == "*" or self.peek() == "**" or self.ahead() == "=" else 0
            self.extra += w  # (an argument after the first, or a keyword or star one, is deeper)
            if self.peek() == "*" or self.peek() == "**":
                star = "starred" if self.peek() == "*" else "dstar"
                if star == "starred" and keyed == "dstar" and pos == "":
                    self.fail("iterable argument unpacking follows keyword argument unpacking", self.toks[self.p - 1].line)
                if star == "dstar":
                    keyed = "dstar"
                self.p += 1
                c.kids.append(mk(star, "", line, [self.test()]))
                if star == "starred" and self.compnext():
                    self.fail("iterable unpacking cannot be used in comprehension", at)
                if star == "dstar" and self.peek() == "=":
                    self.fail("cannot assign to keyword argument unpacking", at)
            elif (self.peek() == "True" or self.peek() == "False" or self.peek() == "None") and self.ahead() == "=":
                self.fail(f"cannot assign to {self.peek()}", at)
            elif self.peek() == "id" and self.ahead() == "=":
                name = self.toks[self.p].text
                if name in kws:
                    self.later(2, f"keyword argument repeated: {name}", self.line())
                kws[name] = True
                self.no_debug(name, self.line())
                if keyed == "":
                    keyed = "kw"
                self.p += 2
                c.kids.append(mk("kw", name, line, [self.test()]))
                if self.compnext():
                    self.fail("invalid syntax. Maybe you meant '==' or ':=' instead of '='?", at)
            else:
                if keyed != "" and pos == "":
                    pos = "positional argument follows keyword argument" + (" unpacking" if keyed == "dstar" else "")
                a = self.named(True)
                if self.peek() == "=":
                    self.fail('expression cannot contain assignment, perhaps you meant "=="?', start(a))
                if self.compnext():
                    if gen == 0:
                        gen = start(a)
                    fl = self.line()
                    a = self.comp(a, line)
                    a.s = "gen"
                    if cls and len(c.kids) == n and self.peek() == ")":
                        self.invalid(fl)  # (class C(x for x in y): only a call takes one)
                c.kids.append(a)
            self.extra -= w
            if not self.eat(","):
                self.expect(")")
                break
            if gen > 0:
                self.fail("Generator expression must be parenthesized", gen)
        if gen > 0 and len(c.kids) > n + 1:
            self.fail("Generator expression must be parenthesized", gen)
        if pos != "":
            self.fail(pos, self.toks[self.p - 1].line)

    def subscript(self, line: int) -> Node:
        # one item of a subscript: an expression, *x, or lo:hi[:step] (a "sliceitem")
        if self.peek() == "*":
            return self.item()
        lo = mk("omit", "", line, [])
        p = self.p
        if self.peek() != ":":
            lo = self.named()
        if not self.eat(":"):
            return lo
        if lo.kind == "walrus" and self.toks[p].kind == "id":
            self.invalid(self.toks[self.p - 1].line)  # (x[a := 1:2]: a bound is an expression)
        n = mk("sliceitem", "", line, [lo, mk("omit", "", line, [])])
        if self.peek() != "]" and self.peek() != ":" and self.peek() != ",":
            n.kids[1] = self.test()
        if self.eat(":") and self.peek() != "]" and self.peek() != ",":
            self.extra += 1
            n.kids.append(self.test())
            self.extra -= 1
        return n

    def comp(self, e: Node, line: int) -> Node:
        # [e for t in it if c]; with more for and if clauses a "nestedcomp" node, with async for
        # an "asynccomp" one, whose clauses after the first iterable are "compif" (kids: the
        # condition) and "compfor" (the target, the iterable) nodes; s is "async" for an async for
        # clause (the first: of the node itself, until a generator expression's is "gen")
        if e.kind == "starred":
            self.fail("iterable unpacking cannot be used in comprehension", e.line)
        aio = self.eat("async")
        self.expect("for")
        t = self.targets()
        self.expect("in")
        n = mk("listcomp", "async" if aio else "", line, [e, t, self.or_test()])
        ts = [t]
        while self.compnext() or self.peek() == "if":
            if self.eat("if"):
                n.kids.append(mk("compif", "", line, [self.or_test()]))
            else:
                a = self.eat("async")
                aio = a or aio
                self.p += 1
                ts.append(self.targets())
                self.expect("in")
                n.kids.append(mk("compfor", "async" if a else "", line, [ts[-1], self.or_test()]))
        if len(n.kids) > 4 or len(ts) > 1:
            n.kind = "nestedcomp"
        elif len(n.kids) == 4 and not aio:
            n.kids[3] = n.kids[3].kids[0]  # [e for t in it if c]
        if aio:
            n.kind = "asynccomp"
        return n

    def atom(self) -> Node:
        self.peek()
        t = self.toks[self.p]
        self.p += 1
        k = t.kind
        line = t.line
        if k == "id":
            return mk("name", t.text, line, [])
        if k == "int" or k == "float" or k == "complex":
            return mk(k, t.text, line, [])
        if k == "...":
            return mk("ellipsis", "", line, [])
        if k == "await":
            # await x: x is a primary (await -x, await await x and await not x are invalid)
            a = self.peek()
            if a not in STARTS or a == "-" or a == "+" or a == "~" or a == "not" or a == "lambda" or a == "yield" or a == "await":
                self.invalid(self.line())
            return mk("await", "", line, [self.postfix()])
        if k == "yield":
            self.invalid(line)  # (a yield expression stands only where rhs() parses it, or in parentheses)
        if k == "str" or k == "fstr" or k == "rfstr" or k == "bytes":
            # adjacent literals concatenate; any f-string among them makes the whole an f-string.
            # CPython decodes each in turn, then checks that all or none are bytes.
            parts: list[Tok] = [t]
            while self.peek() == "str" or self.peek() == "fstr" or self.peek() == "rfstr" or self.peek() == "bytes":
                parts.append(self.toks[self.p])
                self.p += 1
            n = mk("fstr", "", line, [])
            nb = 0
            for pt in parts:
                if pt.kind == "bytes":
                    self.bytes_check(pt)
                    nb += 1
                elif pt.kind == "str":
                    n.kids.append(mk("str", self.unescape(pt.text, pt.line) if pt.esc else pt.text, pt.line, []))
                else:
                    self.fparts(pt.text, pt.kind == "rfstr", pt.line, n)
            if nb > 0 and nb < len(parts):
                self.fail("cannot mix bytes and nonbytes literals", self.line())
            if nb > 0:
                return mk("bytes", "", line, [])
            plain = True
            for kd in n.kids:
                if kd.kind != "str":
                    plain = False
            if plain:
                return mk("str", "".join([kd.s for kd in n.kids]), line, [])
            return n
        if k == "None" or k == "True" or k == "False":
            return mk(k, "", line, [])
        if k == "(":
            if self.eat(")"):
                return mk("tuple", "", line, [])
            if self.peek() == "yield":
                e = self.yield_()
                if self.peek() != ")":
                    self.invalid(self.line())
                self.p += 1
                return e
            e = self.nitem()
            if self.compnext():
                e = self.comp(e, line)
                e.s = "gen"
            elif self.peek() == ",":
                e = mk("tuple", "", line, [e])
                self.extra += 3  # (later items are 2 or 3 levels deeper in CPython's parser)
                while self.eat(","):
                    if self.peek() == ")":
                        break
                    e.kids.append(self.nitem())
                self.extra -= 3
            elif e.kind == "starred" and self.peek() == ")":
                self.fail("cannot use starred expression here", e.line)
            self.expect(")")
            return e
        if k == "[":
            items: list[Node] = []
            if self.peek() != "]":
                e = self.nitem()
                if self.compnext():
                    e = self.comp(e, line)
                    self.expect("]")
                    return e
                items.append(e)
                self.extra += 1
                while self.eat(","):
                    if self.peek() == "]":
                        break
                    items.append(self.nitem())
                self.extra -= 1
                if self.compnext():
                    self.fail("did you forget parentheses around the comprehension target?", start(items[0]))
            self.expect("]")
            return mk("list", "", line, items)
        if k == "{":
            # a dict display; set displays and comprehensions, and dict comprehensions, are their own
            # nodes. A dict's items are key: value and **x, a set's x and *x, never both.
            d = mk("dict", "", line, [])
            seen = 0  # the items so far
            while not self.eat("}"):
                at = self.line()
                self.extra += 1 if seen == 1 else 0
                if self.eat("**"):
                    if d.kind == "set":
                        self.invalid(at)
                    d.kind = "dstar"
                    d.kids.append(self.binary(0))
                    if self.peek() == ":":
                        self.invalid(self.line())
                else:
                    p = self.p
                    e = self.nitem()
                    if self.peek() != ":":
                        if seen > 0 and d.kind != "set" and e.kind == "starred":
                            self.invalid(start(e))
                        if seen > 0 and d.kind != "set":
                            self.fail("':' expected after dictionary key", start(e))
                        d.kind = "set"
                        d.kids.append(e)
                    else:
                        if d.kind == "set" or e.kind == "starred" or (e.kind == "walrus" and self.toks[p].kind == "id"):
                            self.invalid(self.line())
                        self.p += 1
                        if self.peek() == "*":
                            self.fail("cannot use a starred expression in a dictionary value", self.line())
                        if self.peek() == "}" or self.peek() == ",":
                            self.fail("expression expected after dictionary key and ':'", self.toks[self.p - 1].line)
                        d.kids.append(e)
                        d.kids.append(self.test())
                seen += 1
                if self.compnext():
                    if d.kind == "dstar" and seen > 1:
                        self.invalid(at)
                    if d.kind == "dstar":
                        self.fail("dict unpacking cannot be used in dict comprehension", at)
                    if d.kind == "set" and len(d.kids) > 1:
                        self.fail("did you forget parentheses around the comprehension target?", start(d.kids[0]))
                    if len(d.kids) > 2:
                        self.invalid(self.line())
                    # (a dict comprehension's element is the tuple of its key and value)
                    c = self.comp(d.kids[-1] if d.kind == "set" else mk("tuple", "", line, d.kids[-2:]), line)
                    d = mk("dictcomp" if d.kind == "dict" else "setcomp", "", line, [c])
                    self.expect("}")
                    break
                if not self.eat(","):
                    self.expect("}")
                    break
            self.extra -= 1 if seen > 1 else 0
            return d
        if k == "indent":
            fail("unexpected indent", line)  # (CPython reports it as it finds it)
        self.invalid(line)
        return mk("omit", "", line, [])

    def fparts(self, s: str, raw: bool, line: int, n: Node) -> None:
        # the parts of an f-string body (or of a format spec with nested fields), appended to n:
        # literal text as str nodes, each replacement field as fmt(expression, spec). (Errors of
        # CPython's tokenizer in an f-string are reported where they are, with fail().)
        lit: list[str] = []
        i = 0
        while i < len(s):
            c = s[i]
            if (c == "{" or c == "}") and s[i + 1 : i + 2] == c:
                lit.append(c)
                i += 2
            elif c == "}":
                fail("f-string: single '}' is not allowed", line)
            elif c == "{":
                # the expression ends at a top-level '}', ':' or '!' (but not '!='); its text
                # leaves out the comments in it, which run to the end of their line
                j = i + 1
                depth = 0
                code: list[str] = []
                while j < len(s) and (depth > 0 or not (s[j] == "}" or s[j] == ":" or (s[j] == "!" and s[j + 1 : j + 2] != "="))):
                    k = j + 1
                    if s[j] == "'" or s[j] == '"':
                        while k < len(s) and s[k] != s[j]:
                            k += 2 if s[k] == "\\" else 1
                        if k >= len(s):
                            fail("f-string: unterminated string", line)
                        k += 1
                    elif s[j] == "#":
                        k = s.find("\n", j)
                        j = len(s) if k < 0 else k
                        continue
                    elif s[j] == "(" or s[j] == "[" or s[j] == "{":
                        depth += 1
                    elif s[j] == ")" or s[j] == "]" or s[j] == "}":
                        depth -= 1
                        if depth < 0:
                            fail(f"f-string: unmatched '{s[j]}'", line)
                    code.append(s[j:k])
                    j = k
                if j >= len(s):
                    self.fail("f-string: expecting '}'", line)
                self.flush(lit, raw, line, n)
                lit = []
                text = "".join(code)
                src = text.rstrip()
                selfdoc = src.endswith("=") and not (src.endswith("==") or src.endswith("!=") or src.endswith("<=") or src.endswith(">="))
                if selfdoc:
                    # f"{x=}" prints the expression's text, then its value
                    n.kids.append(mk("str", text, line, []))
                    src = src[:-1]
                if src.strip() == "":
                    self.fail("f-string: valid expression required before '}'", line)
                lam = src.strip()
                if lam.startswith("lambda") and not (lam[6:7].isalnum() or lam[6:7] == "_") and s[j] == ":":
                    self.fail("f-string: lambda expressions are not allowed without parentheses", line)
                # (in parentheses, an expression may continue over lines: f"""{x\n + 1}"""); an
                # error at the closing parenthesis is on the field's last line
                toks = Lexer("(" + src.strip() + "\n)", line).run()
                last = line + src.strip().count("\n")
                for t in toks:
                    t.line = min(t.line, last)
                sub = Parser(toks)
                sub.nest = self.nest
                sub.extra = self.extra + 5  # (33 levels in CPython's parser, 28 for parentheses)
                sub.outer = self.outer + [self.toks]
                sub.outerp = self.outerp + [self.p]
                sub.expect("(")
                e = sub.no_star(sub.rhs())
                if sub.peek() != ")":
                    sub.fail("f-string: invalid syntax", line)
                for cat in [0, 2]:
                    if sub.errs[cat] != "":
                        self.later(cat, sub.errs[cat], sub.at[cat])
                conv = ""
                if s[j] == "!":
                    # !r, !s or !a, right after the '!'; then (white space and) ':' or '}'
                    k = self.fskip(s, j + 1)
                    m = k
                    while m < len(s) and ((s[m].isalnum() and ord(s[m]) < 128) or s[m] == "_"):
                        m += 1
                    conv = s[k:m]
                    if conv == "" and (s[k : k + 1] == ":" or s[k : k + 1] == "}"):
                        self.fail("f-string: missing conversion character", line)
                    if conv == "" or (conv[0] >= "0" and conv[0] <= "9"):
                        self.fail("f-string: invalid conversion character", line)
                    if k > j + 1:
                        self.fail("f-string: conversion type must come right after the exclamation mark", line)
                    if conv != "r" and conv != "s" and conv != "a":
                        self.fail(f"f-string: invalid conversion character '{conv}': expected 's', 'r', or 'a'", line)
                    j = self.fskip(s, m)
                    if j >= len(s) or (s[j] != ":" and s[j] != "}"):
                        self.fail("f-string: expecting ':' or '}'", line)
                spec = mk("str", "", line, [])
                if j < len(s) and s[j] == ":":
                    # the spec runs to the matching '}' and may hold nested fields: {x:>{w}}
                    k = j + 1
                    depth = 0
                    while k < len(s) and (depth > 0 or s[k] != "}"):
                        if s[k] == "{":
                            depth += 1
                        elif s[k] == "}":
                            depth -= 1
                        k += 1
                    st = s[j + 1 : k]
                    if "{" in st:
                        spec = mk("fstr", "", line, [])
                        self.fparts(st, raw, line, spec)
                    else:
                        spec = mk("str", st if raw else self.unescape(st, line), line, [])
                    j = k
                if j >= len(s) or s[j] != "}":
                    self.fail("f-string: expecting '}'", line)
                if selfdoc and conv == "" and (spec.kind != "str" or spec.s == ""):
                    conv = "r"
                if conv != "":
                    fn = "__pys_repr" if conv == "r" else ("__pys_str" if conv == "s" else "__pys_ascii")
                    e = mk("call", "", line, [mk("name", fn, line, []), e])
                n.kids.append(mk("fmt", "", line, [e, spec]))
                i = j + 1
            else:
                lit.append(c)
                i += 1
        self.flush(lit, raw, line, n)

    def fskip(self, s: str, j: int) -> int:
        # past the white space and comments from s[j] in a replacement field
        while j < len(s) and (s[j] == " " or s[j] == "\t" or s[j] == "\n" or s[j] == "\r" or s[j] == "\f" or s[j] == "#"):
            if s[j] == "#":
                k = s.find("\n", j)
                j = len(s) if k < 0 else k
            else:
                j += 1
        return j

    def flush(self, lit: list[str], raw: bool, line: int, n: Node) -> None:
        if len(lit) > 0:
            n.kids.append(mk("str", "".join(lit) if raw else self.unescape("".join(lit), line), line, []))

    def unescape(self, s: str, line: int) -> str:
        # decode the backslash escapes of a string literal's source text. CPython's error for an
        # invalid one gives its position in what CPython decodes, where a non-ASCII character is
        # a \U escape of 10 characters (and a backslash before one is \u005c)
        out: list[str] = []
        i = 0
        at = 0  # (CPython's position of s[i])
        n = len(s)
        while i < n:
            c = s[i]
            if c != "\\" or i + 1 >= n or ord(s[i + 1]) >= 128:
                out.append(c)
                at += 6 if c == "\\" else (1 if ord(c) < 128 else (10 if ord(c) >= 192 else 0))
                i += 1
                continue
            e = s[i + 1]
            b = i
            i += 2
            if e == "x" or e == "u" or e == "U":
                k = 2 if e == "x" else (4 if e == "u" else 8)
                h = 0
                while h < k and i + h < n and "0123456789abcdefABCDEF".find(s[i + h]) >= 0:
                    h += 1
                if h < k:
                    self.fail(f"(unicode error) 'unicodeescape' codec can't decode bytes in position {at}-{at + 1 + h}: truncated \\{e}{'X' * k} escape", line)
                v = int(s[i : i + k], 16)
                if v > 1114111:
                    self.fail(f"(unicode error) 'unicodeescape' codec can't decode bytes in position {at}-{at + 1 + k}: illegal Unicode character", line)
                out.append(utf8(v))
                i += k
            elif e >= "0" and e <= "7":
                v = ord(e) - 48
                for _ in range(2):
                    if i < n and s[i] >= "0" and s[i] <= "7":
                        v = v * 8 + ord(s[i]) - 48
                        i += 1
                out.append(utf8(v))
            elif e == "N":
                # \N{name}: CPython's error when it is malformed (a name is a Pystachy limitation)
                k = s.find("}", i)
                if s[i : i + 1] != "{" or k < 0 or k == i + 1:
                    end = at + 1 if s[i : i + 1] != "{" else (at + 2 if k == i + 1 else at + n - b - 1)
                    self.fail(f"(unicode error) 'unicodeescape' codec can't decode bytes in position {at}-{end}: malformed \\N character escape", line)
                self.fail("\\N{...} escapes are not supported", line)
            elif e == "\n":
                pass
            elif e in ESCAPES:
                out.append(ESCAPES[e])
            else:
                out.append("\\" + e)
            at += i - b
        return "".join(out)

    def bytes_check(self, t: Tok) -> None:
        # CPython's errors for a bytes literal: a character that is not ASCII, an \x without two
        # hexadecimal digits
        for c in t.text:
            if ord(c) >= 128:
                self.fail("bytes can only contain ASCII literal characters", t.line)
        k = t.text.find("\\") if t.esc else -1
        while k >= 0:
            if t.text[k + 1 : k + 2] == "x":
                h = t.text[k + 2 : k + 4]
                if len(h) < 2 or "0123456789abcdefABCDEF".find(h[0]) < 0 or "0123456789abcdefABCDEF".find(h[1]) < 0:
                    self.fail(f"(value error) invalid \\x escape at position {k}", t.line)
            k = t.text.find("\\", k + 2)


# ---------------------------------------------------------------- scopes
# CPython checks a whole file before running any of it, but Pystachy compiles a function only
# where the program calls it. So, as each module is parsed, Symtable checks its scopes the way
# CPython's symbol table does (global and nonlocal statements, yield in comprehensions), then
# its analysis does (the bindings nonlocal statements name), then its compiler does (yield, await
# and async outside a function or an async def, async comprehensions, starred targets and values,
# in the order it compiles them, but not in the annotations it never compiles), and reports the
# first error of the first of those. A name's flags in a scope, as CPython's symbol table has them:
SYMPARAM = 1
SYMUSE = 2
SYMLOCAL = 4
SYMANNOT = 8
SYMGLOBAL = 16
SYMNONLOCAL = 32
COMPNAMES: dict[str, str] = {"list": "list comprehension", "set": "set comprehension", "dict": "dict comprehension", "gen": "generator expression"}


class SymScope:
    def __init__(self, kind: str, comp: str, isasync: bool, idx: int):
        # module, class, def, lambda, comp (a comprehension), annotation (a postponed one) or
        # typeparams (those of a generic def or class, around its own scope)
        self.kind = kind
        self.comp = comp  # a comprehension's kind (list, set, dict or gen)
        self.isasync = isasync  # an async def
        self.coro = isasync  # it awaits (CPython's ste_coroutine)
        self.gen = False  # an async def that yields
        self.idx = idx  # its position in the walk
        self.iterexpr = 0  # in a comprehension's iterable
        self.iters: dict[str, bool] = {}  # a comprehension's iteration variables
        self.walrus: dict[str, bool] = {}  # and the names its own := bind so far
        self.flags: dict[str, int] = {}
        self.dirs: dict[str, int] = {}  # the line of each name's first global or nonlocal statement
        self.bound: dict[str, bool] = {}  # the names the enclosing functions bind
        self.inner: dict[str, bool] = {}  # those the scopes nested in it see
        self.tps: dict[str, bool] = {}  # the type parameters among bound (not bound again since)
        self.tpinner: dict[str, bool] = {}  # those the scopes nested in it see
        self.code: bool = kind == "def" or kind == "lambda" or kind == "class" or kind == "typeparams" or comp == "gen"  # a code object
        self.seeclass = False  # a scope of type parameters or of a type alias in a class body (see Symtable.comp)
        self.blocks = 0  # the blocks open in the code object around it (Symtable.depth())
        self.fin = 0  # and its finally blocks open (Symtable.fin)
        self.tuples = 0  # and the tuple displays (Symtable.tuples)


def target_names(t: Node, out: dict[str, bool]) -> None:
    # the names target t binds, into a dict (names_in)
    ns: list[str] = []
    names_in(t, ns)
    for nm in ns:
        out[nm] = True


def walrus_names(e: Node, out: dict[str, bool]) -> None:
    # x := v binds x in the enclosing function, also inside a comprehension or a lambda's
    # defaults (not in its body)
    if e.kind == "walrus":
        out[e.s] = True
    if e.kind == "lambda":
        for p in e.kids[0].kids:
            walrus_names(p.kids[1], out)
    else:
        for k in e.kids:
            walrus_names(k, out)


def scope_binds(body: list[Node], out: dict[str, bool], decl: dict[str, str]) -> None:
    # the names a function's body binds (not those of the functions and classes in it), and in
    # decl those its global and nonlocal statements declare
    for st in body:
        k = st.kind
        if k == "global" or k == "nonlocal":
            for g in st.kids:
                decl[g.s] = k
        elif k == "def":
            # (with its defaults, annotations and decorators, which run here)
            out[st.s] = True
            for p in st.kids[0].kids:
                walrus_names(p.kids[0], out)
                walrus_names(p.kids[1], out)
            for x in [st.kids[1]] + st.kids[3:]:
                walrus_names(x, out)
        elif k == "class" or k == "subclass":
            # (with its decorators and bases)
            c = st if k == "class" else st.kids[0]
            out[c.s] = True
            for x in c.kids[1:] + (st.kids[1:] if k == "subclass" else []):
                walrus_names(x, out)
        elif k == "typealias":
            out[st.s] = True
        elif k == "import":
            for a in st.kids:
                if a.s != "*":
                    out[a.s] = True
        elif k == "assign" or k == "del":
            for t in st.kids if k == "del" else st.kids[:-1]:
                target_names(t, out)
        elif (k == "annassign" and (st.s == "" or len(st.kids) == 3)) or k == "augassign" or k == "for":
            target_names(st.kids[0], out)
        elif k == "with":
            for it in st.kids[:-1]:
                if len(it.kids) == 2:
                    target_names(it.kids[1], out)
        if k != "def" and k != "class" and k != "subclass":
            for kid in st.kids:
                if kid.kind == "block":
                    scope_binds(kid.kids, out, decl)
                elif kid.kind == "except":
                    if kid.s != "":
                        out[kid.s] = True
                    walrus_names(kid.kids[0], out)
                    scope_binds(kid.kids[1].kids, out, decl)
                elif k == "async":
                    scope_binds([kid], out, decl)
                else:
                    for nm in kid.s.split() if kid.kind == "pattern" else []:
                        out[nm] = True  # (a match statement's captures)
                    walrus_names(kid, out)


class Symtable:
    def __init__(self, errs: list[str], at: list[int]):
        # the first error of CPython's symbol table (0), its analysis (1) and its compiler (2), with
        # the parser's of 0 and 2 (see Parser.later)
        self.errs = errs
        self.at = at
        self.keys: list[int] = [at[0], at[1], at[2]]  # what decides the first: the line; in the analysis, the scope
        self.stack: list[SymScope] = []
        self.n = 0
        self.future = False  # from __future__ import annotations: annotations are not evaluated
        self.quiet = 0  # in an annotation that CPython's compiler never compiles: none of its errors
        self.tparams: dict[int, str] = {}  # see Parser.tparams
        self.tpx: dict[int, list[Node]] = {}  # see Parser.tpx
        self.tpann = False  # in a generic def's annotations or a generic class's bases (see comp)
        self.blocks = 0  # the blocks CPython's compiler has open in this code object (see depth())
        self.fin = 0  # the finally blocks among them (see stmt())
        # the first line in them with too many blocks only where exceptions run some of them, and its blocks
        self.exc = 0
        self.exce = 0
        self.citer = False  # in the target of a comprehension's for clause after its first
        self.codes = 0  # the code objects nested here (see push())
        self.tuples = 0  # and the tuple displays in this one
        self.deep = 0  # the line where they first nest too deeply to marshal, in an imported module

    def check(self, body: list[Node], doc: bool) -> None:
        # first the features that the from __future__ imports at the top (after a docstring) choose
        i = 1 if doc else 0
        while i < len(body) and body[i].kind == "import" and body[i].s == "from" and body[i].kids[0].kids[1].s == "__future__":
            for a in body[i].kids:
                x = a.kids[0].s[11:]
                if x == "braces":
                    fail("not a chance", body[i].line)
                if x not in FUTURE and x != "barry_as_FLUFL":
                    fail(f"future feature {x} is not defined", body[i].line)
                if x == "annotations":
                    self.future = True
            i += 1
        self.push("module", "", False)
        self.stmts(body)
        self.pop()
        for c in range(3):
            if self.errs[c] != "":
                fail(self.errs[c], self.at[c])
        if self.deep > 0:
            fail("functions, lambdas, classes and constant tuples nested too deeply: CPython's import of this module fails as it writes its bytecode (ValueError: object too deeply nested to marshal)", self.deep)

    def depth(self, n: int, line: int) -> None:
        # CPython's compiler keeps at most 21 blocks open in a code object (CO_MAXBLOCKS): one for a
        # loop, a with item, a try body (two with finally and except), an except handler's body
        # (two), a finally block and an inlined comprehension (a generator or coroutine has one)
        self.blocks = n
        if n - self.fin > 21:
            self.note(2, "too many statically nested blocks", line)
        elif n > 21 and (self.exc == 0 or n > self.exce):
            # (CPython compiles each finally block's paths in turn: an error on its exception path, and
            # on the normal ones of those around it (n - 21 deep), comes after errors only deeper)
            self.exc = line
            self.exce = n

    def note(self, cat: int, msg: str, line: int) -> None:
        if cat == 2 and self.quiet > 0:
            return
        key = self.stack[-1].idx if cat == 1 else line
        if self.errs[cat] == "" or key < self.keys[cat]:
            self.errs[cat] = msg
            self.at[cat] = line
            self.keys[cat] = key

    def push(self, kind: str, comp: str, isasync: bool, line: int = 0, code: bool = False) -> SymScope:
        sc = SymScope(kind, comp, isasync, self.n)
        sc.code = sc.code or code
        self.n += 1
        if sc.code:
            sc.blocks = self.blocks
            sc.fin = self.fin
            sc.tuples = self.tuples
            self.blocks = 0
            self.fin = 0
            self.tuples = 0
            self.codes += 1
            self.marshal(line)
        if len(self.stack) > 0:
            sc.bound = self.stack[-1].inner
            sc.inner = sc.bound
            sc.tps = self.stack[-1].tpinner
            sc.tpinner = sc.tps
            sc.iterexpr = self.stack[-1].iterexpr  # (a lambda or comprehension in an iterable is in it too)
        if kind == "class":
            # (its methods see __class__)
            sc.inner = dict(sc.bound)
            sc.inner["__class__"] = True
            sc.inner["__classdict__"] = True
        self.stack.append(sc)
        return sc

    def marshal(self, line: int) -> None:
        # CPython's marshal writes at most 2,000 levels: a code object nested in others is 2 deeper
        # (and its constants' tuple), and a constant tuple 1 (a tuple display may be one)
        if 2 * self.codes + self.tuples + 3 > 2000 and line >= LINES and self.deep == 0:
            self.deep = line

    def pop(self) -> None:
        # CPython's analysis of the scope's global and nonlocal names
        sc = self.stack[-1]
        for nm in sc.dirs:
            f = sc.flags[nm]
            if (f & SYMGLOBAL) != 0 and (f & SYMNONLOCAL) != 0:
                self.note(1, f"name '{nm}' is nonlocal and global", sc.dirs[nm])
            elif (f & SYMNONLOCAL) != 0 and sc.kind == "module":
                self.note(1, "nonlocal declaration not allowed at module level", sc.dirs[nm])
            elif (f & SYMNONLOCAL) != 0 and nm not in sc.bound:
                self.note(1, f"no binding for nonlocal '{nm}' found", sc.dirs[nm])
            elif (f & SYMNONLOCAL) != 0 and nm in sc.tps:
                self.note(1, f"nonlocal binding not allowed for type parameter '{nm}'", sc.dirs[nm])
        if sc.code:
            self.blocks = sc.blocks
            self.fin = sc.fin
            self.tuples = sc.tuples
            self.codes -= 1
        self.stack.pop()

    def flag(self, name: str, f: int) -> None:
        sc = self.stack[-1]
        sc.flags[name] = sc.flags.get(name, 0) | f

    def stmts(self, body: list[Node]) -> None:
        for st in body:
            self.stmt(st)

    def stmt(self, st: Node) -> None:
        sc = self.stack[-1]
        k = st.kind
        if k == "def":
            self.flag(st.s, SYMLOCAL)
            for p in st.kids[0].kids:
                self.expr(p.kids[1])
            for d in st.kids[3:]:
                self.deco(d)
            blocks = self.blocks
            fin = self.fin
            tpann = self.tpann
            if st.line in self.tparams:
                self.blocks = 0  # (a generic def's annotations are compiled in its type parameters' scope)
                self.fin = 0
                self.tpann = True
            for p in st.kids[0].kids:
                self.annotation(p.kids[0], False)
            self.annotation(st.kids[1], False)
            self.blocks = blocks
            self.fin = fin
            self.tpann = tpann
            self.function(st)
        elif k == "class" or k == "subclass":
            c = st if k == "class" else st.kids[0]
            self.flag(c.s, SYMLOCAL)
            blocks = self.blocks
            fin = self.fin
            tpann = self.tpann
            if c.line in self.tparams:
                self.blocks = 0  # (and a generic class's bases)
                self.fin = 0
                self.tpann = True
            for b in st.kids[1:] if k == "subclass" else []:
                self.expr(b)
            self.blocks = blocks
            self.fin = fin
            self.tpann = tpann
            for d in c.kids[1:]:
                self.deco(d)
            self.generic(c.line)
            cs = self.push("class", "", False, c.line)
            own: dict[str, bool] = {}
            decl: dict[str, str] = {}
            scope_binds(c.kids[0].kids, own, decl)
            self.rebind(cs, own)
            self.stmts(c.kids[0].kids)
            self.pop()
            if c.line in self.tparams:
                self.pop()
        elif k == "global" or k == "nonlocal":
            for g in st.kids:
                f = sc.flags.get(g.s, 0)
                msg = ""
                if (f & SYMPARAM) != 0:
                    msg = f"name '{g.s}' is parameter and {k}"
                elif (f & SYMUSE) != 0:
                    msg = f"name '{g.s}' is used prior to {k} declaration"
                elif (f & SYMANNOT) != 0:
                    msg = f"annotated name '{g.s}' can't be {k}"
                elif (f & SYMLOCAL) != 0:
                    msg = f"name '{g.s}' is assigned to before {k} declaration"
                if msg != "":
                    self.note(0, msg, st.line)
                self.flag(g.s, SYMGLOBAL if k == "global" else SYMNONLOCAL)
                if g.s not in sc.dirs:
                    sc.dirs[g.s] = st.line
        elif k == "annassign":
            t = st.kids[0]
            if t.kind == "name" and st.s == "":
                f = sc.flags.get(t.s, 0)
                if (f & (SYMGLOBAL | SYMNONLOCAL)) != 0 and sc.kind != "module":
                    self.note(0, f"annotated name '{t.s}' can't be {'global' if (f & SYMGLOBAL) != 0 else 'nonlocal'}", st.line)
                self.flag(t.s, SYMANNOT | SYMLOCAL)
            elif len(st.kids) == 3 or t.kind != "name":
                self.target(t)
            self.annotation(st.kids[1], sc.kind == "def")
            for v in st.kids[2:]:
                self.expr(v)
            self.store(t)
        elif k == "assign" or k == "augassign" or k == "del":
            for i in range(len(st.kids)):
                if k == "del" or i < len(st.kids) - 1:
                    self.target(st.kids[i])
                else:
                    self.expr(st.kids[i])
            for t in st.kids[:-1] if k == "assign" else []:
                self.store(t)  # (once the value is computed, as CPython's compiler stores it)
            t = st.kids[0]
            if k == "augassign" and t.kind == "name" and t.s == "__debug__":
                self.note(2, "cannot assign to __debug__", t.line)  # (x.__debug__ += 1 is valid)
        elif k == "for":
            base = self.blocks
            self.depth(base + 1, st.line)  # (the target and the iterable are compiled in the loop's block)
            self.target(st.kids[0])
            self.expr(st.kids[1])
            self.store(st.kids[0])
            for b in st.kids[2:]:
                self.stmts(b.kids)
                self.blocks = base
        elif k == "with":
            base = self.blocks
            for it in st.kids[:-1]:
                self.expr(it.kids[0])
                self.depth(self.blocks + 1, start(it.kids[0]))
                if len(it.kids) == 2:
                    self.target(it.kids[1])
                    self.store(it.kids[1])
            self.stmts(st.kids[-1].kids)
            self.blocks = base
        elif k == "typealias":
            self.flag(st.s, SYMLOCAL)
            self.dropped(st.line)
        elif k == "import":
            for a in st.kids:
                if a.s == "*" and sc.kind != "module":
                    self.note(0, "import * only allowed at module level", st.line)
        elif k == "async":
            if not sc.isasync:
                self.note(2, f"'async {st.kids[0].kind}' outside async function", st.line)
            self.stmt(st.kids[0])
        else:
            if k == "return" and len(st.kids) > 0 and sc.gen:
                self.note(2, "'return' with value in async generator", st.line)
            base = self.blocks
            fin = 1 if k == "try" and st.kids[-1].s == "finally" else 0
            herr = ""  # (the compiler's first error before a try's handlers, and the one depth() defers)
            hat = 0
            hkey = 0
            hexc = 0
            hexce = 0
            for kid in st.kids:
                if k == "try" and kid.kind == "except" and kid is st.kids[1]:
                    herr = self.errs[2]
                    hat = self.at[2]
                    hkey = self.keys[2]
                    hexc = self.exc
                    hexce = self.exce
                if (k == "while" or k == "try") and kid is st.kids[0]:
                    self.depth(base + (1 if k == "while" or st.kids[1].kind == "except" else 0) + fin, st.line)
                elif kid.kind == "except":
                    self.depth(base + fin + 2, kid.line)
                elif kid.kind == "block" and (kid.s == "else" or kid.s == "finally"):
                    self.blocks = base + (1 if kid.s == "finally" else fin)
                if kid.kind == "block" and kid.s == "finally":
                    # CPython compiles a finally block where the try ends, and then again where an
                    # exception runs it, with one block more (finally blocks in it, in each of those):
                    # an error only on such a path comes after the others (see depth())
                    key = self.keys[2]
                    exc = self.exc
                    exce = self.exce
                    self.exc = self.exc if self.fin > 0 else 0
                    self.fin += 1
                    self.stmts(kid.kids)
                    self.fin -= 1
                    if self.fin == 0 and self.exc > 0 and self.keys[2] == key:
                        self.note(2, "too many statically nested blocks", self.exc)
                    if self.fin == 0:
                        self.exc = exc
                        self.exce = exce
                elif kid.kind == "block" and k == "try" and kid.s == "else":
                    # CPython compiles a try's else block before its handlers: an error there comes first
                    aerr = self.errs[2]
                    aat = self.at[2]
                    akey = self.keys[2]
                    aexc = self.exc
                    aexce = self.exce
                    self.errs[2] = herr
                    self.at[2] = hat
                    self.keys[2] = hkey
                    self.exc = hexc
                    self.exce = hexce
                    self.stmts(kid.kids)
                    if self.errs[2] == herr and self.at[2] == hat:
                        self.errs[2] = aerr
                        self.at[2] = aat
                        self.keys[2] = akey
                    if self.exc == hexc or (aexc != hexc and aexce > self.exce):
                        self.exc = aexc
                        self.exce = aexce
                elif kid.kind == "block":
                    self.stmts(kid.kids)
                elif kid.kind == "except":
                    self.expr(kid.kids[0])
                    if kid.s != "":
                        self.flag(kid.s, SYMLOCAL)
                    self.stmts(kid.kids[1].kids)
                elif kid.kind == "pattern":
                    for nm in kid.s.split():
                        self.flag(nm, SYMLOCAL)
                    for g in kid.kids:
                        self.expr(g)
                else:
                    self.expr(kid)
            self.blocks = base

    def deco(self, d: Node) -> None:
        if len(d.kids) > 0:
            self.expr(d.kids[0])
        elif d.s != "async":
            self.flag(d.s[: d.s.find(".")] if "." in d.s else d.s, SYMUSE)

    def annotation(self, e: Node, local: bool) -> None:
        # evaluated where the def or the annotated assignment is; a postponed one (from __future__
        # import annotations) in a scope of its own, where yield, await and := are errors. CPython's
        # compiler never compiles a postponed one or one in a function body (local).
        if e.kind == "noann":
            return
        if local or self.future:
            self.quiet += 1
        if self.future:
            self.push("annotation", "", False)
        self.expr(e)
        if self.future:
            self.pop()
        if local or self.future:
            self.quiet -= 1

    def rebind(self, sc: SymScope, own: dict[str, bool]) -> None:
        # a type parameter that scope sc binds again is none to the scopes nested in it
        sc.tpinner = {}
        for nm in sc.tps:
            if nm not in own:
                sc.tpinner[nm] = True

    def generic(self, line: int) -> None:
        # the type parameters of the generic def or class on line: in a scope of their own, around
        # its scope (and their own type parameters to a nonlocal statement in it)
        if line not in self.tparams:
            return
        sc = self.push("typeparams", "", False, line)
        sc.seeclass = self.stack[-2].kind == "class"
        sc.inner = dict(sc.bound)
        sc.tpinner = dict(sc.tps)
        for nm in self.tparams[line].split():
            sc.inner[nm] = True
            sc.tpinner[nm] = True
        self.dropped(line)

    def dropped(self, line: int) -> None:
        # what the def, class or type statement on line evaluates in scopes of its own that the
        # parser drops (Parser.tpx): CPython compiles it with no block open around it, whether or
        # not it runs (a type alias's value and the bounds are evaluated lazily)
        if line not in self.tpx:
            return
        sc = self.push("typeparams", "", False, line)
        sc.seeclass = self.stack[-2].kind == "class" or self.stack[-2].seeclass
        for e in self.tpx[line]:
            if e.kind == "annotation":
                self.annotation(e.kids[0], False)
            else:
                self.expr(e)
        self.pop()

    def function(self, d: Node) -> None:
        # a def's body, in a scope of its own: the names it binds are those its nested functions see
        isasync = False
        for x in d.kids[3:]:
            if x.s == "async" and len(x.kids) == 0:
                isasync = True
        self.generic(d.line)
        sc = self.push("def", "", isasync, d.line)
        own: dict[str, bool] = {}
        decl: dict[str, str] = {}
        for p in d.kids[0].kids:
            own[p.s] = True
            sc.flags[p.s] = SYMPARAM
        scope_binds(d.kids[2].kids, own, decl)
        sc.inner = dict(sc.bound)
        for nm in decl:
            if decl[nm] == "global" and nm in sc.inner:
                del sc.inner[nm]
        for nm in own:
            if nm not in decl:
                sc.inner[nm] = True
        self.rebind(sc, own)
        sc.gen = isasync and has_kind(d.kids[2], "yield")
        self.blocks = 1 if isasync or has_kind(d.kids[2], "yield") else 0
        self.stmts(d.kids[2].kids)
        self.pop()
        if d.line in self.tparams:
            self.pop()

    def target(self, t: Node) -> None:
        # an assigned (or deleted) target: its names are bound, the rest of it is read
        if t.kind == "name":
            self.iter_name(t)
            self.flag(t.s, SYMLOCAL)
        elif t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
            for k in t.kids:
                self.target(k)
        else:
            self.expr(t)

    def iter_name(self, n: Node) -> None:
        # a name in the target of a comprehension's for clause after its := of that name
        if self.citer and n.s in self.stack[-1].walrus:
            self.note(0, f"comprehension inner loop cannot rebind assignment expression target '{n.s}'", n.line)

    def store(self, t: Node) -> None:
        # CPython's compiler checks of an assignment target: where starred items go, and __debug__
        k = t.kind
        if k == "starred":
            self.note(2, "starred assignment target must be in a list or tuple", t.line)
        elif k == "tuple" or k == "list":
            stars = 0
            for i in range(len(t.kids)):
                if t.kids[i].kind == "starred":
                    stars += 1
                    if stars == 1 and i >= 256:
                        self.note(2, "too many expressions in star-unpacking assignment", t.line)
            if stars > 1:
                self.note(2, "multiple starred expressions in assignment", t.line)
            for x in t.kids:
                self.store(x.kids[0] if x.kind == "starred" else x)
        elif (k == "name" or k == "attr") and t.s == "__debug__":
            self.note(2, "cannot assign to __debug__", t.line)

    def expr(self, e: Node) -> None:
        sc = self.stack[-1]
        k = e.kind
        if (k == "yield" or k == "await" or k == "walrus") and sc.kind == "annotation":
            self.note(0, f"{'named' if k == 'walrus' else k} expression cannot be used within an annotation", e.line)
        if k == "starred" and e.s == "here":
            self.note(2, "can't use starred expression here", e.line)  # (see Parser.no_star)
        if k == "name":
            self.iter_name(e)
            self.flag(e.s, SYMUSE)
        elif k == "tuple":
            self.tuples += 1
            self.marshal(e.line)
            for kid in e.kids:
                self.expr(kid)
            self.tuples -= 1
        elif k == "lambda":
            for p in e.kids[0].kids:
                self.expr(p.kids[1])
            ls = self.push("lambda", "", False, e.line)
            for p in e.kids[0].kids:
                ls.flags[p.s] = SYMPARAM
            self.expr(e.kids[1])
            self.pop()
        elif k == "listcomp" or k == "nestedcomp" or k == "asynccomp":
            self.comp(e, "gen" if e.s == "gen" else "list")
        elif k == "setcomp" or k == "dictcomp":
            self.comp(e.kids[0], k[:-4])
        elif k == "walrus":
            # x := v in a comprehension binds x in the function around it
            if sc.iterexpr > 0:
                self.note(0, "assignment expression cannot be used in a comprehension iterable expression", e.line)
            i = len(self.stack) - 1
            while self.stack[i].kind == "comp" or self.stack[i].kind == "annotation":
                if e.s in self.stack[i].iters:
                    self.note(0, f"assignment expression cannot rebind comprehension iteration variable '{e.s}'", e.line)
                i -= 1
            if sc.kind == "comp" and self.stack[i].kind == "class":
                self.note(0, "assignment expression within a comprehension cannot be used in a class body", e.line)
            self.expr(e.kids[0])
            self.stack[i].flags[e.s] = self.stack[i].flags.get(e.s, 0) | SYMLOCAL
            if sc.kind == "comp":
                sc.walrus[e.s] = True
            if e.s == "__debug__":
                self.note(2, "cannot assign to __debug__", e.line)
        elif k == "yield":
            # (CPython's compiler checks where a yield is before its value, its symbol table where
            # a comprehension's is after it)
            if sc.kind == "module" or sc.kind == "class":
                self.note(2, "'yield from' outside function" if e.s == "from" else "'yield' outside function", e.line)
            elif e.s == "from" and sc.isasync:
                self.note(2, "'yield from' inside async function", e.line)
            for kid in e.kids:
                self.expr(kid)
            if sc.kind == "comp":
                self.note(0, f"'yield' inside {COMPNAMES[sc.comp]}", e.line)
        elif k == "await":
            sc.coro = True
            i = len(self.stack) - 1
            while self.stack[i].kind == "comp" and self.stack[i].comp != "gen":
                i -= 1  # (a list, set or dict comprehension runs in the scope around it)
            up = self.stack[i]
            if up.kind == "module" or up.kind == "class":
                self.note(2, "'await' outside function", e.line)
            elif (up.kind == "def" and not up.isasync) or up.kind == "lambda":
                self.note(2, "'await' outside async function", e.line)
            self.expr(e.kids[0])
        else:
            for kid in e.kids:
                self.expr(kid)

    def comp(self, c: Node, kind: str) -> None:
        # a comprehension: its first iterable is evaluated outside it, the rest in a scope of its
        # own; an asynchronous one (async for, await) must be in an async def
        up = self.stack[-1]
        up.iterexpr += 1
        self.expr(c.kids[2])
        up.iterexpr -= 1
        base = self.blocks
        n = 1
        for x in [c] + c.kids[3:]:
            n += 1 if x.s == "async" and (x is c or x.kind == "compfor") else 0
        # (CPython inlines a list, set or dict comprehension, but not where it can see a class's
        # names: in the scope of type parameters or of a type alias in a class body, where it is a
        # function of its own, as a generator expression is)
        own = kind == "gen" or up.seeclass or (self.tpann and up.kind == "class")
        if not own:
            self.depth(base + n, c.line)  # (a comprehension that is inlined, and each async for clause)
        err = self.errs[2]  # (CPython's compiler checks that before it compiles the rest)
        at = self.at[2]
        key = self.keys[2]
        sc = self.push("comp", kind, False, c.line, own)
        sc.coro = c.kind == "asynccomp"
        target_names(c.kids[1], sc.iters)
        self.target(c.kids[1])
        self.store(c.kids[1])
        for x in c.kids[3:]:
            if x.kind == "compfor":
                target_names(x.kids[0], sc.iters)
                self.citer = True
                self.target(x.kids[0])
                self.citer = False
                sc.iterexpr += 1
                self.expr(x.kids[1])
                sc.iterexpr -= 1
                self.store(x.kids[0])
            else:
                self.expr(x)
        self.expr(c.kids[0])
        self.pop()
        self.blocks = base
        if sc.coro and kind != "gen":
            if up.kind != "comp" and not ((up.kind == "def" or up.kind == "lambda") and up.coro) and self.quiet == 0:
                self.errs[2] = err
                self.at[2] = at
                self.keys[2] = key
                self.note(2, "asynchronous comprehension outside of an asynchronous function", c.line)
            up.coro = True


# ---------------------------------------------------------------- modules
# A program may import Python modules: the package NAME/__init__.py or the file NAME.py found
# first next to the main program, on PYSTACHY_PATH or in the lib/ directory beside the compiler
# (the builtin modules, sys, os, math and the others in MODULES, come before them). The loader
# parses each module once and rewrites its AST so that every module-level name is qualified by
# the module's name (heapq$heappush: "$" cannot occur in an identifier) and every reference
# through a module (heapq.heappush, or heappush after from heapq import heappush) is that name.
# Code generation then sees one program with no module objects in it. A module's top-level code
# runs as the function @init.<module> the first time an import of it runs ("uimport" nodes).
class Mod:
    def __init__(self, name: str, path: str, pdir: str):
        self.name = name  # the dotted module name; "" for the main program
        self.path = path  # its file; "" for a namespace package
        self.pdir = pdir  # the directory of its submodules if it is a package, else ""
        self.q: str = name.replace(".", "$") + "$" if name != "" else ""  # prefix of its qualified names
        self.body = mk("block", "", 1, [])
        # what each module-level name binds: "f" a def, "c" a class, "v" a variable, "m:<module>"
        # a user module, "a:<qualified name>" another module's def or class, "b:<path>" a
        # builtin module or one of its attributes
        self.kinds: dict[str, str] = {}
        self.fnglobal: dict[str, bool] = {}  # the names a function's global statement binds
        self.fnonly: dict[str, bool] = {}  # those its top-level code does not
        self.rebound: dict[str, bool] = {}  # the names it binds other than as os, sys, TYPE_CHECKING (rebound())
        self.spec: dict[str, str] = {}  # and those it binds so (specials()): the module, or "" if two differ
        self.specat: dict[str, int] = {}  # the top-level statement that first does
        self.fails = ""  # the exception its top-level code surely raises, ImportError or ModuleNotFoundError
        # a package's names that an import of the submodule of that name rebinds at a time Pystachy
        # cannot tell (Loader.submodules()); True if that may happen while its own code runs
        self.amb: dict[str, bool] = {}
        # the names its top-level code has surely bound and may have bound so far (Loader.imports()),
        # and whether that code has been loaded to its end
        self.sure: dict[str, bool] = {}
        self.maybe: dict[str, bool] = {}
        self.done = False
        # the names only name = f(...) statements bind, with each f: a TypeVar if every f is typing's
        self.tvars: dict[str, list[Node]] = {}


# Python's builtin names: in an imported module, a name it does not bind is one of these or an
# error (never a name of the main program)
PYBUILTINS: dict[str, bool] = {}
for _k in ("ArithmeticError AssertionError AttributeError BaseException BaseExceptionGroup BlockingIOError BrokenPipeError "
           "BufferError BytesWarning ChildProcessError ConnectionAbortedError ConnectionError ConnectionRefusedError "
           "ConnectionResetError DeprecationWarning EOFError Ellipsis EncodingWarning EnvironmentError Exception ExceptionGroup "
           "False FileExistsError FileNotFoundError FloatingPointError FutureWarning GeneratorExit IOError ImportError "
           "ImportWarning IndentationError IndexError InterruptedError IsADirectoryError KeyError KeyboardInterrupt LookupError "
           "MemoryError ModuleNotFoundError NameError None NotADirectoryError NotImplemented NotImplementedError OSError "
           "OverflowError PendingDeprecationWarning PermissionError ProcessLookupError PythonFinalizationError RecursionError "
           "ReferenceError ResourceWarning RuntimeError RuntimeWarning StopAsyncIteration StopIteration SyntaxError "
           "SyntaxWarning SystemError SystemExit TabError TimeoutError True TypeError UnboundLocalError UnicodeDecodeError "
           "UnicodeEncodeError UnicodeError UnicodeTranslateError UnicodeWarning UserWarning ValueError Warning "
           "ZeroDivisionError abs aiter all anext any ascii bin bool breakpoint bytearray bytes callable chr classmethod "
           "compile complex copyright credits delattr dict dir divmod enumerate eval exec exit filter float format frozenset "
           "getattr globals hasattr hash help hex id input int isinstance issubclass iter len license list locals map max "
           "memoryview min next object oct open ord pow print property quit range repr reversed round set setattr slice "
           "sorted staticmethod str sum super tuple type vars zip").split():
    PYBUILTINS[_k] = True
MODNAMES: dict[str, bool] = {}  # and the names CPython binds in every module
for _k in (MODDUNDERS + " __name__ __debug__ __cached__ __import__ __build_class__").split():
    MODNAMES[_k] = True
# what an annotation that CPython evaluates may hold (Loader.not_type): these nodes, '|' of the
# first five, subscripts of the first two
ANNKINDS: list[str] = ["name", "attr", "index", "binop", "None", "str", "True", "False", "int", "float", "ellipsis", "tuple", "list", "unary", "noann", "starred"]
GENERICS: list[str] = ["list", "dict", "tuple", "set", "frozenset", "type"]


# modules built into CPython 3.13 (as Debian and Ubuntu build it, sys.builtin_module_names): a
# file of that name on the path never replaces them, so Pystachy treats them as missing
CBUILTIN: dict[str, bool] = {}
for _k in ("_abc _ast _bisect _blake2 _codecs _collections _csv _datetime _elementtree _functools _heapq _imp _io _locale "
           "_md5 _opcode _operator _pickle _posixsubprocess _random _sha1 _sha2 _sha3 _signal _socket _sre _stat "
           "_statistics _string _struct _suggestions _symtable _sysconfig _thread _tokenize _tracemalloc _typing _warnings "
           "_weakref array atexit binascii cmath faulthandler fcntl gc grp itertools marshal posix pwd pyexpat select "
           "syslog unicodedata zlib").split():
    CBUILTIN[_k] = True


# the kinds of nodes whose code calls no function or method of the program (Loader.raises_in())
NOCALL: dict[str, bool] = {}
for _k in ("name str int float None True False list tuple dict attr assign annassign expr pass global import alias "
           "uimport guard badimport block raise def params param starparam dstarparam noann class").split():
    NOCALL[_k] = True


def builtin_module(path: str) -> bool:
    root = path[: path.find(".")] if "." in path else path
    return path in MODULES or root in MODULES or path == "collections.abc"


def known_path(p: str) -> bool:
    # a module attribute Pystachy implements: a CALLS entry, a modattr() value, a module, or
    # a function builtin() handles itself
    if p in MODULES or p in MODATTRS or p == "sys.exit" or p == "os.fspath" or p == "os.path.join" or p == "os.PathLike" or (p.startswith("errno.") and p[6:] in ERRNO):
        return True
    for k in CALLS:
        if k.startswith(p + "(") or k.startswith(p + "."):
            return True
    return False


def builtin_has(mod: str, x: str) -> bool:
    # may from mod import x name x, of Pystachy's builtin module mod
    if mod == "__future__":
        return x in FUTURE
    if mod == "typing":
        return x in TYPING
    if mod == "collections.abc":
        return x in ABCS
    if mod == "dataclasses":
        return x == "dataclass"
    return mod == "builtins" or known_path(mod + "." + x)  # (a builtin is checked where it is called)


def accel_try(st: Node) -> bool:
    # try: <import statements, then others> / except ImportError: (or ModuleNotFoundError),
    # without finally
    if st.kind != "try" or len(st.kids) < 2 or st.kids[1].kind != "except" or len(st.kids[0].kids) == 0 or st.kids[0].kids[0].kind != "import":
        return False
    seen = False
    for x in st.kids[0].kids:
        if x.kind != "import":
            seen = True
        elif seen:
            return False
    for h in st.kids[1:]:
        if h.kind == "block" and h.s == "finally":
            return False
        if h.kind == "except":
            ts = h.kids[0].kids if h.kids[0].kind == "tuple" else [h.kids[0]]
            for t in ts:
                if t.kind != "name" or (t.s != "ImportError" and t.s != "ModuleNotFoundError"):
                    return False
    return True


def catches_import(st: Node) -> bool:
    # may an except clause of try statement st catch ImportError (a bare except, or one naming it,
    # ModuleNotFoundError, Exception or BaseException)
    for h in st.kids[1:]:
        if h.kind == "except" and h.kids[0].kind == "omit":
            return True
        for t in (h.kids[0].kids if h.kids[0].kind == "tuple" else [h.kids[0]]) if h.kind == "except" else h.kids[:0]:
            if t.kind == "name" and (t.s == "ImportError" or t.s == "ModuleNotFoundError" or t.s == "Exception" or t.s == "BaseException"):
                return True
    return False


def is_main_guard(e: Node) -> bool:
    # __name__ == "__main__"
    if e.kind != "cmp" or e.s != "==":
        return False
    a = e.kids[0]
    b = e.kids[1]
    if a.kind == "str":
        c = a
        a = b
        b = c
    return a.kind == "name" and a.s == "__name__" and b.kind == "str" and b.s == "__main__"


def has_all(body: list[Node]) -> bool:
    # does a module's top-level code assign __all__ (which from m import * then takes)
    for st in body:
        if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s == "__all__":
            return True
    return False


def import_error(e: Node) -> str:
    # "ImportError" or "ModuleNotFoundError" if raise e raises it, else ""
    n = e.kids[0] if e.kind == "call" else e
    return n.s if n.kind == "name" and (n.s == "ImportError" or n.s == "ModuleNotFoundError") else ""


def may_end(n: Node, bare: bool) -> bool:
    # does n hold, outside the functions and classes it defines, a raise that re-raises (bare), or
    # else anything that may end the program: a raise, or a call of exit(), quit(), sys.exit(),
    # os._exit() or os.abort()
    if n.kind == "raise" and (len(n.kids) == 0 or not bare):
        return True
    for x in n.kids[:1] if n.kind == "call" and not bare else n.kids[:0]:
        if (x.kind == "name" and (x.s == "exit" or x.s == "quit")) or (x.kind == "attr" and (x.s == "exit" or x.s == "_exit" or x.s == "abort")):
            return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass":
        return False
    for k in n.kids:
        if may_end(k, bare):
            return True
    return False


def special_import(st: Node, a: Node) -> bool:
    # an import the loader recognizes where the name it binds is read: of a builtin module (import
    # os, import os.path as p), or from typing import TYPE_CHECKING
    if st.s == "":
        return builtin_module(a.kids[1].s)
    return st.s == "from" and (a.kids[0].s == "typing.TYPE_CHECKING" or a.kids[0].s == "typing_extensions.TYPE_CHECKING")


def binds(body: list[Node], out: dict[str, bool], special: bool, pkg: str = "", deep: bool = True) -> None:
    # the names statements bind in their own scope (not inside the functions and classes they
    # define): assignments, del, def and class, except ... as, and imports (only with special those
    # special_import() recognizes; "*" for a star import; but in package pkg's code its own
    # from . import x of its submodule x, which binds x to that unless x is bound already); not in
    # their blocks unless deep
    for st in body:
        targets(st, out)
        if st.kind == "import":
            for a in st.kids:
                own = pkg != "" and a.s == a.kids[0].s[a.kids[0].s.rfind(".") + 1 :] and ((st.s == "from." and a.kids[1].s == "") or (st.s == "from" and a.kids[1].s == pkg))
                if (special or a.s == "*" or not special_import(st, a)) and not own:
                    out[a.s] = True
        elif st.kind == "del":
            for t in st.kids:
                if t.kind == "name":
                    out[t.s] = True
        elif st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            out[st.s] = True
            continue
        for kid in st.kids:
            if kid.kind == "block" and deep:
                binds(kid.kids, out, special, pkg)
            elif kid.kind == "except" and (special or not builtin_try(st)):
                if kid.s != "":
                    out[kid.s] = True
                binds(kid.kids[1].kids, out, special, pkg)


def builtin_try(st: Node) -> bool:
    # an optional import of builtin modules only (try: from typing import TYPE_CHECKING / except
    # ImportError: TYPE_CHECKING = False), whose except clauses never run (Loader.optional())
    for x in st.kids[0].kids if accel_try(st) else st.kids[:0]:
        for a in x.kids if x.kind == "import" else x.kids[:0]:
            if x.s.startswith("from.") or not (builtin_module(a.kids[1].s) or a.kids[1].s == "typing_extensions"):
                return False
    return accel_try(st)


def surely_binds(st: Node, out: dict[str, bool], bound: dict[str, bool], deep: bool = True) -> None:
    # the names statement st binds for sure once it has run, at its own level and in a with block
    # (not in its other blocks); a del, also in those blocks, removes the names it may delete from
    # out and bound. Not deep: the statements in st's blocks have been through it already, with
    # the same bound (Loader.imports), so only a with block's are looked at again (for out)
    if st.kind != "for" and not (st.kind == "annassign" and len(st.kids) < 3):
        targets(st, out)
    gone: dict[str, bool] = {}
    if st.kind == "import":
        for a in st.kids:
            if a.s != "*":
                out[a.s] = True
    elif st.kind == "def" or st.kind == "class" or st.kind == "subclass":
        out[st.s] = True
    elif st.kind == "with":
        for s in st.kids[-1].kids:
            surely_binds(s, out, bound)
    else:
        deleted([st] if deep or st.kind == "del" else [], gone)
    for nm in gone:
        for d in [out, bound]:
            if nm in d:
                del d[nm]


def specials(m: Mod, body: list[Node], top: int, sure: bool = False) -> None:
    # the names module m's code (body; top: the index of the top-level statement it is in, or -1 for
    # the top level; sure: the body of an optional import of builtin modules there) binds by the
    # imports special_import() recognizes, with what they bind, "" if two differ (Mod.spec), and the
    # top-level statement with the first that binds each for sure
    for i in range(len(body)):
        st = body[i]
        for a in st.kids if st.kind == "import" else st.kids[:0]:
            if special_import(st, a):
                t = a.kids[0].s if st.s == "" else "typing.TYPE_CHECKING"
                m.spec[a.s] = t if m.spec.get(a.s, t) == t else ""
                if (top < 0 or sure) and a.s not in m.specat:
                    m.specat[a.s] = i if top < 0 else top
        for kid in st.kids if st.kind != "def" and st.kind != "class" and st.kind != "subclass" else st.kids[:0]:
            if kid.kind == "block":
                specials(m, kid.kids, i if top < 0 else top, top < 0 and kid is st.kids[0] and builtin_try(st))
            elif kid.kind == "except":
                specials(m, kid.kids[1].kids, i if top < 0 else top)


def rebound(body: list[Node], special: bool) -> dict[str, bool]:
    # the names a module binds (but for special, by the imports special_import() recognizes), also
    # through a function's global statement: such a name is never taken for os, sys or TYPE_CHECKING
    out: dict[str, bool] = {}
    binds(body, out, special)
    for st in body:
        fns = [st] if st.kind == "def" else st.kids[0].kids if st.kind == "class" else st.kids[:0]
        for d in fns:
            if d.kind == "def":
                decl: dict[str, bool] = {}
                asg: dict[str, bool] = {}
                globals_in(d.kids[2].kids, decl)
                binds(d.kids[2].kids, asg, True)
                for nm in decl:
                    if nm in asg:
                        out[nm] = True
    return out


def own_specials(d: Node) -> Mod:
    # what def d binds by its own imports that special_import() recognizes (Mod.spec, as specials()
    # finds it), and its other names: its parameters, globals and what it binds otherwise
    # (Mod.rebound)
    f = Mod("", "", "")
    body = d.kids[2].kids
    specials(f, body, -1)
    binds(body, f.rebound, False)
    globals_in(body, f.rebound)
    for p in d.kids[0].kids:
        f.rebound[p.s] = True
    return f


def scope_names(st: Node) -> dict[str, bool]:
    # the names a def (its parameters and what its body binds, but its globals) or a class body binds
    # in its own scope, where they hide the module's names
    out: dict[str, bool] = {}
    body = st.kids[2].kids if st.kind == "def" else st.kids[0].kids
    decl: dict[str, bool] = {}
    if st.kind == "def":
        for p in st.kids[0].kids:
            out[p.s] = True
        globals_in(body, decl)
    binds(body, out, True)
    for x in body:
        bound_in(x, out)
    for nm in decl:
        if nm in out:
            del out[nm]
    return out


def bound_in(n: Node, out: dict[str, bool]) -> None:
    # the names that code n binds by :=, also in its comprehensions, by a match statement's captures
    # or by a type statement (not in the functions, classes and lambdas it defines): the compiler
    # rejects these, but in code that is dropped they still make the names local
    if n.kind == "walrus" or n.kind == "typealias" or n.kind == "pattern":
        for nm in n.s.split():
            out[nm] = True
    for k in n.kids if n.kind != "def" and n.kind != "class" and n.kind != "subclass" and n.kind != "lambda" else n.kids[:0]:
        bound_in(k, out)


class Loader:
    def __init__(self, dirs: list[str]):
        self.dirs = dirs  # the module search path
        self.mods: dict[str, Mod] = {}
        self.order: list[Mod] = []  # every module after those its top-level code imports
        # imports in the functions of imported modules, resolved once all module-level imports
        # are loaded: the function may never be compiled, as CPython may never run it
        self.later: list[Node] = []
        self.laterm: list[Mod] = []
        self.laterb: list[Node] = []
        self.laterd: list[str] = []
        # what the imports in a function bind (for that function only), by the def's line
        self.fks: dict[str, dict[str, str]] = {}
        self.fgl: dict[str, dict[str, bool]] = {}  # and the names its global statements declare
        self.curdef = ""  # the def whose body imports() is in
        self.fk: dict[str, str] = {}  # the bindings of the function being qualified
        self.fkey = ""  # and its def's line
        # the try statements imports() is in; the names that imports in try statements bind ("<module>
        # <def line, or empty> <name>"), which the import may leave unbound (Node.mchk), each with the
        # module whose code then did not end; and the names imports outside try statements bind
        self.intry = 0
        self.optry = False  # (in the body of one whose clauses may catch ImportError: not an optional import)
        self.fragile: dict[str, str] = {}
        self.solid: dict[str, bool] = {}
        self.parsed: dict[str, Node] = {}  # each module file, parsed once
        # and what its code binds, surely and maybe, as scan() finds it before it is loaded
        self.rawbound: dict[str, dict[str, bool]] = {}
        # and those of the code of the module whose code is being simplified, up to statement ownpos
        self.ownkids: list[Node] = []
        self.ownpos = 0
        self.ownsure: dict[str, bool] = {}
        self.ownmaybe: dict[str, bool] = {}
        self.rawsure: dict[str, dict[str, bool]] = {}
        self.failc: dict[str, str] = {}  # what init_fails() found for a module not loaded yet
        self.scanning: dict[str, bool] = {}  # the modules init_fails() is looking at
        # the index of the top-level statement whose code simplify() or init_raise() is in, -1 in a
        # function
        self.pos = -1
        # the names that the top-level code imports() is in has surely bound by then, and those it
        # may have bound (for take())
        self.sure: dict[str, bool] = {}
        self.maybe: dict[str, bool] = {}
        # each optional import that optional() decided: s is the module whose import fails, if its
        # code raises ImportError, and the kids are the other modules whose code runs in the try;
        # with the module it is in, and the other statements that run in the try (checked by guarded())
        self.sites: list[Node] = []
        self.sitem: list[Mod] = []
        self.siterest: list[Node] = []
        # what raises() found for a module, where that does not depend on the modules whose code was
        # running (rcyc: a result that did); the function fn_raises() found, "?" before it looks
        self.rmemo: dict[str, int] = {}
        self.rcyc = False
        self.fn = "?"
        # each from-import of a name a package binds itself (take()), with the bindings it went to,
        # for submodules(): s is the name bound, the kids the package, the name and the copy if any
        self.taken: list[Node] = []
        self.takek: list[dict[str, str]] = []
        # each star import of a package without __all__, with the module it is in (submodules())
        self.stars: list[Node] = []
        self.starm: list[Mod] = []
        self.qdef = False  # is qstmts() in a function
        # the function simplify() is in (own_specials()), and the names that its own imports which
        # special_import() recognizes have surely bound where simplify() is
        self.fs = Mod("", "", "")
        self.fsure: dict[str, bool] = {}
        self.unsure: dict[str, dict[str, bool]] = {}  # what each def reads before an import of it surely ran (import_reads())
        self.lazyann = False  # the module deftime() walks imports annotations from __future__
        self.called = 0  # and its code may have called a function by now (1), or imported a module (2)
        self.dm = Mod("", "", "")  # (that module)
        self.bdecos: dict[int, bool] = {}  # the decorators, by line, that surely name a builtin
        # the names of dm's code that deftime() has seen bound to a class without bases, decorators
        # or __class_getitem__ (a type, which CPython cannot subscript) and not bound again since
        self.known: dict[str, bool] = {}

    def program(self, path: str, src: str) -> list[Mod]:
        # the main program and the modules it imports, in the order their code may first run
        m = Mod("", path, "")
        FILES.append(path)
        m.body = Parser(Lexer(src, 1).file()).module()
        self.prescan(m)
        self.simplify(m, m.body, {})
        self.bindings(m)
        self.sure = m.sure
        self.maybe = m.maybe
        self.imports(m, m.body, False)
        self.order.append(m)
        for i in range(len(self.later)):
            st = self.later[i]
            self.curdef = self.laterd[i]
            out: list[Node] = []
            if self.loaded(self.laterm[i], st):
                self.import_stmt(self.laterm[i], st, True, out)
            else:
                for a in st.kids:
                    p = a.kids[1].s if not st.s.startswith("from.") else self.relative(self.laterm[i], st.s, a.kids[1].s, st.line)
                    msg = f"importing module '{p}' in a function of module '{self.laterm[i].name}' is not supported: the program's module-level code does not import it"
                    if p in self.mods and st.s.startswith("from"):
                        xn = a.kids[0].s[a.kids[0].s.rfind(".") + 1 :]
                        msg = f"cannot import name '{xn}' from '{p}'"
                    out.append(mk("badimport", msg, st.line, []))
                    self.bind(self.laterm[i], a.s, "x:" + msg, True, st.line)
            b = self.laterb[i]
            for j in range(len(b.kids)):
                if b.kids[j] is st:
                    b.kids = b.kids[:j] + out + b.kids[j + 1 :]
                    break
        self.guarded()
        self.submodules()
        for x in self.order:
            self.late_aliases(x)
        for x in self.order:
            self.lazyann = False
            self.called = 0
            self.dm = x
            self.known = {}
            env: list[dict[str, bool]] = [{}, {}, {}, {}]  # (a package binds __path__, annotations __annotations__)
            mark((["__path__"] if x.pdir != "" else []) + (["__annotations__"] if has_kind(x.body, "annassign") else []), env[0], env[1], [])
            self.deftime(x, x.body.kids, env, "", [], True)
        for x in self.order:
            self.qstmts(x, x.body.kids, {}, False)
        return self.order

    def loaded(self, m: Mod, st: Node) -> bool:
        # are the user modules import statement st names (and from-imported submodules) loaded
        for a in st.kids:
            p = a.kids[1].s
            if st.s.startswith("from."):
                p = self.relative(m, st.s, p, st.line)
            elif builtin_module(p) or p == "typing_extensions":
                continue
            if p not in self.mods:
                return False
            if st.s.startswith("from") and a.s != "*":
                x = a.kids[0].s[a.kids[0].s.rfind(".") + 1 :]
                if x not in self.mods[p].kinds and p + "." + x not in self.mods:
                    return False
        return True

    def modpath(self, name: str) -> str:
        # the file module name is loaded from: NAME/__init__.py or NAME.py, the first found on the
        # module path or in the parent package, else the directories of a namespace package
        # (separated by ":"); "" if there is none
        if name in CBUILTIN:
            return ""  # a module built into CPython: no file on the path replaces it
        dirs = self.dirs
        base = name
        dot = name.rfind(".")
        if dot >= 0:
            par = self.modpath(name[:dot])
            if par.endswith("/__init__.py"):
                dirs = [par[:-12]]
            elif par != "" and not par.endswith(".py"):
                dirs = par.split(":")
            else:
                return ""
            base = name[dot + 1 :]
        for d in dirs:
            p = d + "/" + base
            if os.path.exists(p + "/__init__.py"):
                return p + "/__init__.py"
            if os.path.exists(p + ".py"):
                return p + ".py"
        found: list[str] = []
        for d in dirs:
            if os.path.exists(d + "/" + base):
                found.append(d + "/" + base)
        return ":".join(found)

    def find(self, name: str, line: int) -> Mod:
        # the user module called name, loaded with its parent packages unless it is already
        if name in self.mods:
            return self.mods[name]
        dot = name.rfind(".")
        if dot >= 0:
            par = self.find(name[:dot], line)
            if par.pdir == "":
                fail(f"No module named '{name}'; '{par.name}' is not a package", line)
            if name in self.mods:
                return self.mods[name]  # the package's own code imported it
        p = self.modpath(name)
        if p == "":
            # (an optional import other than try: <imports> / except ImportError:, which optional() decides)
            hint = "; an optional import is supported only as try: <imports> / except ImportError: (except clauses naming only ImportError or ModuleNotFoundError, and no finally)" if self.optry else ""
            fail(f"module '{name}' is not supported: it is not a builtin module ({', '.join(MODULES.keys())}) and there is no {name[dot + 1 :]}.py on the module path{hint}", line)
        if p.endswith("/__init__.py"):
            return self.load(name, p, p[:-12])
        if p.endswith(".py"):
            return self.load(name, p, "")
        # a namespace package: a directory without __init__.py
        m = Mod(name, "", p)
        self.mods[name] = m
        self.order.append(m)
        return m

    def load(self, name: str, path: str, pdir: str) -> Mod:
        m = Mod(name, path, pdir)
        self.mods[name] = m
        m.body = self.parse(path)
        del self.parsed[path]  # (m rewrites its tree: the file imported under another name is parsed again)
        self.prescan(m)
        r: list[Node] = []
        if self.init_raise(m, m.body.kids, r, True):
            r[0].s = "init"  # (an optional import of the module returns there instead: Gen.raise_stmt)
            m.fails = import_error(r[0].kids[0])
        self.simplify(m, m.body, {})
        self.bindings(m)
        sure = self.sure
        maybe = self.maybe
        self.sure = m.sure
        self.maybe = m.maybe
        self.imports(m, m.body, False)
        self.sure = sure
        self.maybe = maybe
        m.done = True
        self.order.append(m)
        return m

    def parse(self, path: str) -> Node:
        # a module's file, parsed once for the looks before it is loaded (optional()) and the load
        if path in self.parsed:
            return self.parsed[path]
        f = open(path, "r", encoding="latin-1")
        src = f.read()
        f.close()
        k = len(FILES)
        FILES.append(path[2:] if path.startswith("./") else path)
        self.parsed[path] = Parser(Lexer(src, k * LINES + 1).file()).module()
        return self.parsed[path]

    def bindings(self, m: Mod) -> None:
        # the names m's top-level code binds (imports of user modules are added by imports())
        count = top_bindings(m.body.kids)
        aliases: list[Node] = []
        for st in m.body.kids:
            k = st.kind
            src = m.kinds.get(st.kids[1].s, "") if k == "assign" and len(st.kids) == 2 and st.kids[1].kind == "name" else ""
            if src != "" and st.kids[0].kind == "name" and (src == "f" or src == "c" or src.startswith("a:")) and count[st.kids[0].s] == 1:
                # name = a def or class of this module (or an alias of one): an alias, if nothing
                # else binds name
                m.kinds[st.kids[0].s] = src if src.startswith("a:") else "a:" + m.q + st.kids[1].s
                aliases.append(st)
            elif k == "def" or k == "class" or k == "subclass":
                m.kinds[st.s] = "f" if k == "def" else "c"
                for d in [st] if k == "def" else st.kids[0].kids if k == "class" else st.kids[0].kids[0].kids:
                    if d.kind == "def":
                        decl: dict[str, bool] = {}
                        asg: dict[str, bool] = {}
                        globals_in(d.kids[2].kids, decl)
                        collect(d.kids[2].kids, asg)
                        for nm in decl:
                            if nm in asg:
                                m.fnglobal[nm] = True
                            if nm in asg and nm not in m.kinds:
                                m.kinds[nm] = "v"
                                m.fnonly[nm] = True
            elif k != "import":
                names: dict[str, bool] = {}
                collect([st], names)
                for nm in names:
                    m.kinds[nm] = "v"
                    if nm in m.fnonly:
                        del m.fnonly[nm]
                if k == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[1].kind == "call":
                    # (T = TypeVar("T"), also more than once: see Loader.typevar)
                    if st.kids[0].s not in m.tvars:
                        m.tvars[st.kids[0].s] = []
                    m.tvars[st.kids[0].s].append(st.kids[1].kids[0])
        for nm in m.tvars:
            if len(m.tvars[nm]) != count[nm]:
                m.tvars[nm] = []  # (another statement binds it too)
        for al in aliases:
            if al.kids[0].s in m.fnglobal:
                m.kinds[al.kids[0].s] = "v"  # a function's global statement rebinds it
            else:
                al.kind = "pass"
                self.used_before(m, al)

    def late_aliases(self, m: Mod) -> None:
        # name = f where an import binds f (from m import f): an alias too, if nothing else binds name
        count = top_bindings(m.body.kids)
        for st in m.body.kids:
            if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[1].kind == "name":
                src = m.kinds.get(st.kids[1].s, "")
                nm = st.kids[0].s
                if src.startswith("a:") and m.kinds.get(nm, "") == "v" and count.get(nm, 0) == 1 and nm not in m.fnglobal:
                    m.kinds[nm] = src
                    st.kind = "pass"
                    self.used_before(m, st)

    def used_before(self, m: Mod, al: Node) -> None:
        # an alias (name = f) binds name for all of the module's code; module-level code that runs
        # before it would see name unbound in CPython
        nm = al.kids[0].s
        for st in m.body.kids:
            if st is al:
                return
            if st.kind != "def" and st.kind != "class" and st.kind != "subclass" and refers(st, nm):
                fail(f"name '{nm}' is used before '{nm} = {al.kids[1].s}' binds it (not supported for an alias of a function or class)", st.line)

    def deftime(self, m: Mod, body: list[Node], env: list[dict[str, bool]], cls: str, added: list[str], top: bool) -> None:
        # CPython evaluates a def statement's decorators, defaults and annotations, a class
        # statement's decorators and bases, and runs its body, used or not: what they read must be
        # bound then. env: the names surely bound so far, those bound on some path, then a class
        # body's own (in class body cls). An annotation (unless imported from __future__) needs
        # surely bound names, and what it or a base raises is an error (reads); the rest, in an
        # imported module, may read its variables and functions that may be unbound (checked as
        # they run: Gen.effect, read). added: the names body binds that were not surely bound,
        # unbound after a block (not top) but what both if branches bind
        mod = f"when module '{m.name}' is imported" if m.name != "" else ""
        sure = env[2] if cls != "" else env[0]
        maybe = env[3] if cls != "" else env[1]
        for st in body:
            k = st.kind
            imp = top and cls == "" and m.name != "" and self.called < 2 and has_kind(st, "uimport")
            if imp or (top and cls == "" and self.called == 0 and calls(st, m)):
                # (from a first call on, a function's global statement may bind names; from a first
                # import, a module that imports this one may also assign its builtin names: m.object = 5)
                for nm in m.kinds:
                    if nm in m.fnglobal or (imp and nm in PYBUILTINS):
                        env[1][nm] = True
                        self.known.pop(nm, False)
                self.called = 2 if imp else 1
            for a in st.kids if k == "import" else []:
                self.lazyann = self.lazyann or a.kids[0].s == "__future__.annotations"
            if k == "subclass" and len(st.kids) == 2 and st.kids[1].kind == "name" and st.kids[1].s == "object" and "object" not in env[1] and "object" not in env[3]:
                # class C(object) where object is surely still the builtin: a class without bases
                st.kind = "class"
                st.kids = st.kids[0].kids
                k = "class"
            c = st.kids[0] if k == "subclass" else st
            for x in c.kids[3:] if k == "def" else c.kids[1:] if k == "class" or k == "subclass" else []:
                if x.s.startswith("?"):
                    fail("unsupported decorator: only a dotted name or a call of one is supported (PEP 614)", x.line)
                root = x.s.split(".")[0]
                if root in PYBUILTINS and root not in env[1] and root not in env[3]:
                    self.bdecos[x.line] = True  # (the builtin, whatever the module binds later: qdeco)
                if mod != "" and x.s != "async":
                    self.reads(x.kids[0] if len(x.kids) > 0 else mk("name", root, x.line, []), env, f"CPython evaluates decorator @{x.s} {mod}", 0)
            names: list[str] = []
            plain = False  # (a class without bases, decorators or __class_getitem__: see known)
            if k == "def":
                for p in st.kids[0].kids + [mk("param", "", st.line, [st.kids[1], mk("noann", "", st.line, [])])]:
                    self.ann(p.kids[0], env, "the def statement")
                    if mod != "":
                        self.reads(p.kids[1], env, f"CPython evaluates this default value {mod}", 0)
            elif k == "class" or k == "subclass":
                inner: dict[str, bool] = {"__module__": True, "__qualname__": True}  # (and a generic class's type parameters)
                mark((st.kids[1].s if k == "subclass" and st.kids[1].kind == "typeparams" else "").split() + (["__annotations__"] if has_kind(c.kids[0], "annassign") else []), inner, {}, [])
                tps: list[str] = []
                mark((st.kids[1].s if k == "subclass" and st.kids[1].kind == "typeparams" else "").split(), env[2], {}, tps)
                for b in st.kids[1:] if k == "subclass" else []:
                    # (where the class statement is, with its type parameters; in the main program
                    # too, where a base is an error later: CPython's comes first)
                    self.reads(b, env, f"CPython evaluates the bases of class {st.s}" + (" " + mod if mod != "" else ""), 1)
                for t in tps:
                    env[2].pop(t, False)
                own = dict(inner)
                self.deftime(m, c.kids[0].kids, [env[0], env[1], inner, own], st.s, [], True)
                plain = top and cls == "" and k == "class" and len(st.kids) == 1 and "__class_getitem__" not in own
            elif k == "annassign":
                self.ann(st.kids[1], env, "the class body" if cls != "" else "the annotated assignment")
            first: dict[str, bool] = {}
            for i in range(len(st.kids) if k != "def" and k != "class" and k != "subclass" else 0):
                x = st.kids[i]
                tgt: list[str] = [x.s] if x.kind == "except" and x.s != "" else []
                if x.kind == "block" or x.kind == "except":
                    # (a for's, with's or except's name is bound in its block; after an if, what both bind)
                    if k == "for" and i == 2:
                        names_in(st.kids[0], tgt)
                    for w in st.kids if k == "with" else []:
                        if w.kind == "withitem" and len(w.kids) == 2:
                            names_in(w.kids[1], tgt)
                    inside: list[str] = []
                    mark(tgt, sure, maybe, inside)
                    for nm in tgt if cls == "" else []:
                        self.known.pop(nm, False)
                    self.deftime(m, x.kids if x.kind == "block" else x.kids[1].kids, env, cls, inside, False)
                    for nm in inside:
                        sure.pop(nm, False)
                        if k == "if" and i == 1:
                            first[nm] = True
                        elif k == "if" and nm in first:
                            names.append(nm)
                elif (k == "annassign" and i == 1) or k == "global" or k == "nonlocal":
                    continue
                elif ((k == "assign" or k == "pass") and i < len(st.kids) - 1) or ((k == "annassign" or k == "for") and i == 0):
                    names_in(x, names if k != "for" and (k != "annassign" or len(st.kids) == 3) else tgt)  # (an alias is a "pass")
                elif k == "import":
                    names.extend([x.s] if x.kids[0].s != "builtins." + x.s else [])  # (from builtins import len rebinds nothing)
                elif k == "del":
                    names_in(x, tgt)
                    for nm in tgt:
                        sure.pop(nm, False)
                        if cls == "":
                            self.known.pop(nm, False)
                        if top:
                            maybe.pop(nm, False)  # (surely unbound)
                else:
                    if k == "augassign" and i == 0:
                        names_in(x, names)
                    if cls != "" and mod != "":
                        # (what a class body's other statements read)
                        self.reads(x.kids[0] if x.kind == "withitem" else x, env, f"CPython runs this statement of the body of class {cls} {mod}", 0)
            bound = names + (st.s.split() if k == "def" or k == "class" or k == "subclass" or k == "uimport" else [])
            mark(bound, sure, maybe, added)
            for nm in bound if cls == "" else []:
                self.known.pop(nm, False)
            if plain:
                self.known[st.s] = True

    def ann(self, n: Node, env: list[dict[str, bool]], where: str) -> None:
        # an annotation, which CPython evaluates when where runs unless the module imports
        # annotations from __future__ (a string is a forward reference)
        if not self.lazyann:
            self.reads(n, env, f"CPython evaluates this annotation when {where} runs: quote it, or import annotations from __future__", 3)

    def reads(self, e: Node, env: list[dict[str, bool]], what: str, how: int) -> None:
        # the names expression e reads, which must be bound where CPython evaluates it (what): not
        # those of a lambda's body or of a comprehension's own scope. e is (how) 0 a value, 1 a
        # base or part of one, 2 part of an annotation, 3 an annotation. Operands come first, as
        # CPython evaluates them: in a base or an annotation, what raises then (type_error()) is
        # CPython's error; an annotation reads surely bound names and must be a type (not_type)
        k = e.kind
        nm = e.s
        tps: list[str] = []
        mark(nm.split() if k == "noann" else [], env[2], {}, tps)  # (a generic def's type parameters: Parser.funcdef)
        if k == "name" and "$" not in nm and nm not in env[0] and nm not in env[2] and nm not in PYBUILTINS and nm not in MODNAMES:
            maybe = nm in env[1] or nm in env[3]
            if how >= 2 or (self.dm.kinds.get(nm, "") != "v" and self.dm.kinds.get(nm, "") != "f"):
                fail(f"name '{nm}' {'may be unbound, which is not supported' if maybe else 'is not defined'} ({'import it from typing' if how >= 2 and nm in TYPING else what})", e.line)
        for kid in e.kids[2:3] if k == "listcomp" or k == "nestedcomp" or k == "asynccomp" else [] if k == "lambda" else e.kids:
            self.reads(kid, env, what, how if how < 3 or k == "noann" else 2)
        why = self.type_error(e, env) if how > 0 else ""
        for t in tps:
            env[2].pop(t, False)
        if why != "":
            fail(f"{why} ({what})", e.line)
        if how >= 2 and self.not_type(e, how == 3):
            fail(f"an annotation that is not a type is not supported: only classes, typing's names, their subscripts and '|' of them ({what})", e.line)
        if how >= 2 and k == "attr":
            e.chk = True  # (an attribute a module lacks is CPython's AttributeError: qann)

    def type_error(self, e: Node, env: list[dict[str, bool]]) -> str:
        # the TypeError CPython raises evaluating e, a subscript or '|' whose operands it has
        # evaluated (as far as evaltype() knows them), or ""
        k = e.kind
        if k != "index" and not (k == "binop" and e.s == "|"):
            return ""
        ts = [self.evaltype(x, env) for x in e.kids]
        if k == "index" and ts[0] == "type":
            return f"type '{e.kids[0].s}' is not subscriptable"
        have = len(e.kids[1].kids) if k == "index" and e.kids[1].kind == "tuple" else 1
        want = {"typing.Optional": 1, "typing.List": 1, "typing.Dict": 2}.get(ts[0], have) if k == "index" else have
        if want != have and ts[0] == "typing.Optional":
            return "typing.Optional requires a single type"  # (CPython adds the arguments' reprs)
        if want != have:
            return f"Too {'many' if have > want else 'few'} arguments for {ts[0]}; actual {have}, expected {want}"
        if k == "binop" and "" not in ts and not ts[0].startswith("typing.") and not ts[1].startswith("typing.") and ("str" in ts or (ts[0] == "NoneType" and ts[1] == "NoneType")):
            return f"unsupported operand type(s) for |: '{ts[0]}' and '{ts[1]}'"
        return ""

    def evaltype(self, e: Node, env: list[dict[str, bool]]) -> str:
        # what operand e of a subscript or '|' evaluates to, as far as type_error() needs it: "type" (a
        # builtin class, or a class of the module that is in known), "str", "NoneType", a typing
        # name ("typing.Optional"), or "" if it may be anything else
        if e.kind == "str" or e.kind == "None":
            return "str" if e.kind == "str" else "NoneType"
        if e.kind != "name" or e.s in env[2] or e.s in env[3]:
            return ""  # (a class body's or a type parameter)
        if e.s in self.known or (e.s in ["int", "float", "str", "bool", "bytes", "object", "complex"] and e.s not in env[1]):
            return "type"
        b = self.kind_of(e)
        return b[2:] if b.startswith("b:typing.") else ""

    def not_type(self, e: Node, top: bool) -> bool:
        # may annotation node e (top: the whole annotation) run code of the program, or raise,
        # when CPython evaluates it: a variable (but as the whole annotation, an alias, whose value
        # is only stored), a call, an operator but '|' of types, a subscript of what is not
        # typing's or a builtin generic
        k = e.kind
        b = e.kids[0] if k == "index" or k == "binop" or k == "unary" else e
        if k == "binop":
            return e.s != "|" or b.kind not in ANNKINDS[:5] or e.kids[1].kind not in ANNKINDS[:5]
        if k == "unary":
            return e.s != "-" or (b.kind != "int" and b.kind != "float")  # (Literal[-1])
        if k == "index" and (b.kind not in ANNKINDS[:2] or self.kind_of(b) == "f" or self.kind_of(b) == "c" or self.kind_of(b).startswith("a:")):
            return True
        p = self.bpath(e) if k == "attr" else ""
        if p != "" and not p.startswith("typing.") and p != "os.PathLike" and p != "collections.abc" and not (p.startswith("collections.abc.") and p[16:] in ABCS):
            return True  # (a builtin module may lack the attribute)
        return k not in ANNKINDS or (self.kind_of(b) == "v" and not (top and k == "name") and not (k == "name" and self.typevar(e))) or (k == "index" and self.kind_of(b) == "" and b.s in PYBUILTINS and b.kind == "name" and b.s not in GENERICS)

    def bpath(self, e: Node) -> str:
        # what a name or an attribute chain on one names in a builtin module ("collections.abc.Mapping"), or ""
        if e.kind == "name":
            k = self.kind_of(e)
            return k[2:] if k.startswith("b:") else ""
        p = self.bpath(e.kids[0]) if e.kind == "attr" else ""
        return p + "." + e.s if p != "" else ""

    def typevar(self, e: Node) -> bool:
        # is name e a module global that only e = TypeVar(...) statements bind, typing's (each one
        # is Gen.typevar_def's): '|' of it and subscripts holding it run typing's code
        if e.s not in self.dm.tvars or len(self.dm.tvars[e.s]) == 0 or e.s in self.dm.fnglobal:
            return False
        for c in self.dm.tvars[e.s]:
            if self.bpath(c) != "typing.TypeVar":
                return False
        return True

    def kind_of(self, e: Node) -> str:
        # what a name, or an attribute of a user module (a.b), is bound to in module dm, or ""
        if e.kind == "name":
            return self.dm.kinds.get(e.s, "")
        b = self.kind_of(e.kids[0]) if e.kind == "attr" else ""
        return self.mods[b[2:]].kinds.get(e.s, "") if b.startswith("m:") and b[2:] in self.mods else ""

    def simplify(self, m: Mod, blk: Node, scope: dict[str, bool]) -> None:
        # what the loader decides about blk before anything else (scope: the names that the function
        # or class blk is in binds itself, which hide the module's): the if statements and optional
        # imports CPython decides at import time (static_if(), optional()) leave what runs in their
        # place; a module-level alias of a def or class (bisect = bisect_right) binds the same
        # function or class, and is no statement at run time
        out: list[Node] = []
        added: list[str] = []  # (what an import in blk binds is sure only within blk)
        for i in range(len(blk.kids)):
            st = blk.kids[i]
            if blk is m.body:
                self.pos = i
            if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "attr" and st.kids[0].s == "__doc__" and st.kids[0].kids[0].kind == "name" and blk is m.body:
                # f.__doc__ = g.__doc__: docstrings cannot be read in Pystachy, so this is dropped
                continue
            run: list[Node] = []
            if self.static_if(m, st, scope, run) or self.optional(m, st, run, False):
                b = mk("block", "", st.line, run)
                self.simplify(m, b, scope)
                out.extend(b.kids)
            else:
                out.append(st)
                for a in st.kids if st.kind == "import" and not (blk is m.body) else st.kids[:0]:
                    if special_import(st, a) and a.s not in self.fsure:
                        self.fsure[a.s] = True
                        added.append(a.s)
                c = st.kids[0] if st.kind == "subclass" else st  # (class C(object) too: see deftime)
                inner = scope_names(c) if c.kind == "def" or c.kind == "class" else scope
                decl: dict[str, bool] = {}
                types: dict[str, Node] = {}
                pos = self.pos
                fs = self.fs
                fsure = self.fsure
                if st.kind == "def":
                    globals_in(st.kids[2].kids, decl)
                    local_types(st.kids[2].kids, types)
                    self.pos = -1
                    self.fs = own_specials(st)
                    self.fsure = {}
                for kid in c.kids:
                    if kid.kind == "block":
                        self.simplify(m, kid, inner)
                    elif kid.kind == "except":
                        self.simplify(m, kid.kids[1], inner)
                self.pos = pos
                self.fs = fs
                self.fsure = fsure
                if st.kind == "def":
                    self.dropped_locals(st, inner, decl, types)
        for nm in added:
            del self.fsure[nm]
        blk.kids = out

    def dropped_locals(self, d: Node, before: dict[str, bool], decl: dict[str, bool], types: dict[str, Node]) -> None:
        # what function d binds only in code simplify() dropped still decides its scope in CPython: a
        # global statement there holds for the whole function (it is kept), and a name bound there is
        # a local that nothing binds, so a read of it raises UnboundLocalError. It is declared, with
        # the type of a binding that was dropped (types: x: T, or x = <constant>), as x: T declares
        # it; if none gives one, it is an error where d is compiled
        now: dict[str, bool] = {}
        globals_in(d.kids[2].kids, now)
        for nm in decl:
            if nm not in now:
                d.kids[2].kids.insert(0, mk("global", "", d.line, [mk("name", nm, d.line, [])]))
        now = scope_names(d)
        for nm in before:
            msg = f"'{nm}' is local to {d.s}() only through code that is dropped at compile time (for the platform, TYPE_CHECKING or an import that fails), so a read of it raises UnboundLocalError; that is supported only where the dropped code annotates it with a supported type or assigns it a constant"
            if nm not in now and reads(d.kids[2], nm) and nm in types:
                # (where the type is not supported, the message is msg: Gen.stmt())
                t = types[nm]
                d.kids[2].kids.insert(0, mk("annassign", msg, t.line, [mk("name", nm, t.line, []), t]))
            elif nm not in now and reads(d.kids[2], nm):
                d.kids[2].kids.insert(0, mk("badimport", msg, d.line, []))
        early: dict[str, bool] = {}
        user: dict[str, bool] = {}
        import_reads(d.kids[2], {}, early, user)
        self.unsure[str(d.line)] = {}
        for nm in early:
            if nm in user:
                self.unsure[str(d.line)][nm] = True

    def static_if(self, m: Mod, st: Node, scope: dict[str, bool], out: list[Node]) -> bool:
        # an if statement CPython decides at import time, as Pystachy does at compile time: a test of
        # the platform, of TYPE_CHECKING or in an imported module of __name__ == "__main__"
        # (decide()). Appends what runs to out; False if st is none of these
        if st.kind != "if":
            return False
        pre: list[Node] = []
        r = self.decide(m, st.kids[0], scope, pre)
        if r < 0:
            return False
        out.extend(pre)
        out.extend(st.kids[1].kids if r == 1 else st.kids[2].kids)
        return True

    def optional(self, m: Mod, st: Node, out: list[Node], scan: bool) -> bool:
        # try: <imports, then other statements> / except ImportError: <handler> (an optional module,
        # accel_try()), decided at compile time: the imports run in order until one fails, because
        # its module is not found (the code of its packages runs first), because the module's code
        # raises ImportError at its top level (init_raise(): its code before the raise runs, guarded
        # so that it returns there), or because a from-import names what its module neither binds
        # nor has as a submodule. Then the handler that catches the exception runs; if none fails,
        # the rest of the body and the else block do. Appends what runs to out; False if st is not
        # such a try. Unless scan (init_raise() looking ahead), guarded() checks it later
        if not accel_try(st):
            return False
        line = st.line
        site = mk("pass", "", line, [])  # (for guarded(), which may make it an error)
        out.append(site)
        run: list[Node] = []  # the imports that succeed, then the one that fails
        bad = ""  # the module whose import fails
        exc = "ModuleNotFoundError"
        named = ""  # or the name a from-import of module bad fails to bind
        n = 0  # the import statements that run
        for x in st.kids[0].kids:
            if x.kind != "import" or bad != "":
                break
            n += 1
            ok: list[Node] = []
            p = ""
            for a in x.kids:
                p = a.kids[1].s if not x.s.startswith("from.") else self.relative(m, x.s, a.kids[1].s, x.line)
                i = 0
                while i >= 0 and bad == "" and not builtin_module(p) and (len(ok) == 0 or x.s == ""):
                    # each package on the way, then the module (once for a from-import)
                    i = p.find(".", i + 1)
                    q = p[:i] if i >= 0 else p
                    f = self.init_fails(q) if self.modpath(q) != "" else "ModuleNotFoundError"
                    if f != "":
                        bad = q
                        exc = f
                    else:
                        site.kids.append(mk("str", q, line, []))
                if bad != "":
                    break
                ok.append(a)
            subs: list[int] = []  # the names that are submodules, which run their code
            gone = len(x.kids)  # the first name that is neither bound by module p nor a submodule
            for j in range(len(x.kids) if x.s != "" and bad == "" and not builtin_module(p) else 0):
                # CPython's fromlist: each name module p does not bind is imported as its submodule
                # (one that is not found is passed over), then the names are bound
                xn = x.kids[j].kids[0].s[x.kids[j].kids[0].s.rfind(".") + 1 :]
                r = 2 if bad != "" or x.kids[j].s == "*" else self.binds_name(m, p, xn)
                if r == 1:
                    # (CPython's handler runs if x is not bound by then)
                    site.kind = "badimport"
                    site.s = f"cannot tell whether module '{p}' has bound '{xn}' when this optional import runs (it binds '{xn}' in a branch, deletes it, only annotates it, binds it in a function or by a star import, or its code is still running): not supported"
                    site.kids = []
                    return True
                if r == 2:
                    continue
                if self.modpath(p + "." + xn) == "":
                    gone = min(gone, j)
                    continue
                f = self.init_fails(p + "." + xn)
                if f != "":
                    bad = p + "." + xn
                    exc = f
                else:
                    subs.append(j)
                    site.kids.append(mk("str", p + "." + xn, line, []))
            for j in range(len(x.kids) if x.s != "" and bad == "" and builtin_module(p) else 0):
                # a name that Pystachy's builtin module lacks: as one that a module does not bind
                if x.kids[j].s != "*" and not builtin_has(p, x.kids[j].kids[0].s[len(p) + 1 :]):
                    gone = min(gone, j)
            if bad == "" and gone < len(x.kids):
                bad = p
                exc = "ImportError"
                named = x.kids[gone].kids[0].s[x.kids[gone].kids[0].s.rfind(".") + 1 :]
                ok = x.kids[:gone]
            elif bad != "" and x.s != "":
                ok = x.kids[:0]  # (a submodule's ImportError comes before any name is bound)
            if len(ok) == len(x.kids):
                run.append(x)
            elif len(ok) > 0:
                run.append(mk("import", x.s, x.line, ok))
            for j in subs:
                if j >= len(ok):
                    # a submodule that runs its code, though the statement does not bind it
                    sub = p + "." + x.kids[j].kids[0].s[x.kids[j].kids[0].s.rfind(".") + 1 :]
                    run.append(mk("import", "", line, [mk("alias", "", line, [mk("str", sub, line, []), mk("str", sub, line, [])])]))
        h = 0  # the handler that catches the exception
        for j in range(1, len(st.kids)):
            if st.kids[j].kind == "except" and h == 0:
                t = st.kids[j].kids[0]
                for e in t.kids if t.kind == "tuple" else [t]:
                    if e.s == "ImportError" or e.s == exc:
                        h = j
        missing = bad != "" and exc == "ModuleNotFoundError" and self.modpath(bad) == ""
        if bad != "" and not missing and named == "":
            site.s = bad
        if not scan:
            self.sites.append(site)
            self.sitem.append(m)
            self.siterest.append(mk("block", "", line, st.kids[0].kids[n:] if bad == "" else st.kids[0].kids[:0]))
        if bad == "" or h == 0:
            # every import succeeds, or the exception is not caught: the body runs (the failing
            # module's raise ends the program, as in CPython), then the else block
            out.extend(st.kids[0].kids)
            for e in st.kids[1:]:
                if e.kind == "block" and e.s == "else":
                    out.extend(e.kids)
            return True
        b = st.kids[h].kids[1]
        if st.kids[h].s != "" or may_end(b, True) or (missing and may_end(b, False)):
            # the handler needs the exception, or may end the program where the module is not found
            # (CPython may find it: a module of its standard library, or an installed package): the
            # module is required
            if named != "":
                msg = f"cannot import name '{named}' from '{bad}', and an except clause that re-raises or names the exception is not supported"
            elif missing:
                why = "names the exception (as " + short(st.kids[h].s) + ")" if st.kids[h].s != "" else "re-raises the exception" if may_end(b, True) else "may end the program"
                msg = f"module '{bad}' is not supported: it is not a builtin module and there is no {bad[bad.rfind('.') + 1 :]}.py on the module path; an optional import whose except clause {why} needs its module"
            else:
                msg = f"module '{bad}' raises {exc} as it initializes, and an except clause that re-raises or names the exception is not supported"
            out.append(mk("badimport", msg, line, []))
            return True
        out.extend(run)
        par = bad if named != "" else bad[: bad.rfind(".")] if missing and "." in bad else "" if missing else bad
        if par != "" and not builtin_module(par):
            # the code of the failing module's packages runs (and its own until its raise), binding nothing
            al = mk("alias", "", line, [mk("str", par, line, []), mk("str", par, line, [])])
            if not missing and named == "":
                al.kids.append(mk("guard", "", line, []))
            out.append(mk("import", "", line, [al]))
        out.extend(b.kids)
        return True

    def binds_name(self, m: Mod, p: str, x: str) -> int:
        # has module p's code bound x itself when a from-import in module m takes x from it: 2 surely,
        # 1 maybe (in a branch, by a function's global statement or a star import, ...), 0 not. A
        # module not loaded yet runs its code to its end (what static_if() and optional() leave of
        # it); one whose code is running (a circular import, or p is m) has run it up to that import
        path = self.mods[p].path if p in self.mods else self.modpath(p)
        if not path.endswith(".py"):
            return 0  # (a namespace package binds nothing)
        t = self.mods[p] if p in self.mods and p != m.name else Mod(p, path, path[:-12] if path.endswith("/__init__.py") else "")
        maybe = t.maybe
        if p == m.name:
            # (what the statements before it bind, found once for all the optional imports in them)
            end = self.pos if self.pos >= 0 else len(m.body.kids)
            if self.ownkids is not m.body.kids or self.ownpos > end:
                self.ownkids = m.body.kids
                self.ownpos = 0
                self.ownsure = {}
                self.ownmaybe = {}
            for st in m.body.kids[self.ownpos : end]:
                surely_binds(st, self.ownsure, self.ownsure)
                for nm in rebound([st], True):
                    self.ownmaybe[nm] = True
            self.ownpos = end
            t.sure = self.ownsure
            maybe = self.ownmaybe
        elif p not in self.mods:
            if path not in self.rawbound:
                self.scan(t)
            t.sure = self.rawsure[path]
            maybe = self.rawbound[path]
        elif t.done or self.pos < 0:
            maybe = {x: True} if x in t.kinds else {}  # (its code has run to its end, or may have)
        return 2 if x in t.sure else 1 if x in maybe or x in t.fnglobal or "*" in maybe else 0

    def scan(self, t: Mod) -> None:
        # what module t's code binds, not loaded yet: surely (at its top level), and maybe
        self.rawbound[t.path] = {"*": True}  # (while it is scanned: a module that imports t back cannot tell)
        self.rawsure[t.path] = {}
        t.body = self.parse(t.path)
        self.prescan(t)
        pos = self.pos
        fs = self.fs
        self.fs = Mod("", "", "")
        kept: list[Node] = []
        sure: dict[str, bool] = {}
        self.folded(t, t.body.kids, kept, sure, True)
        self.pos = pos
        self.fs = fs
        self.rawbound[t.path] = rebound(kept, True)
        self.rawsure[t.path] = sure

    def folded(self, t: Mod, body: list[Node], kept: list[Node], sure: dict[str, bool], top: bool) -> None:
        # the statements of module t's code (body) that run where static_if() and optional() decide
        # (kept), and the names they surely bind
        for i in range(len(body)):
            if top:
                self.pos = i
            run: list[Node] = []
            if self.static_if(t, body[i], {}, run) or self.optional(t, body[i], run, True):
                self.folded(t, run, kept, sure, False)
            else:
                kept.append(body[i])
                surely_binds(body[i], sure, sure)

    def binds_surely(self, p: str, x: str) -> bool:
        # does module p's code bind x at its top level for sure (not only in an if, try or loop)
        path = self.mods[p].path if p in self.mods else self.modpath(p)
        if not path.endswith(".py"):
            return False
        bound: dict[str, bool] = {}
        for st in self.mods[p].body.kids if p in self.mods else self.parse(path).kids:
            surely_binds(st, bound, bound)
        return x in bound

    def init_fails(self, name: str) -> str:
        # the exception module name's code raises at its top level for sure (init_raise()), or ""
        if name in self.mods:
            return self.mods[name].fails
        p = self.modpath(name)
        if name in self.failc or name in self.scanning or not p.endswith(".py"):
            # (a module whose code imports it back finds it half run; a namespace package has no code)
            return self.failc.get(name, "")
        t = Mod(name, p, p[:-12] if p.endswith("/__init__.py") else "")
        t.body = self.parse(p)
        self.prescan(t)
        r: list[Node] = []
        pos = self.pos
        fs = self.fs
        self.fs = Mod("", "", "")  # (t's code is not in the function simplify() may be in)
        self.scanning[name] = True
        self.init_raise(t, t.body.kids, r, True)
        del self.scanning[name]
        self.pos = pos
        self.fs = fs
        self.failc[name] = import_error(r[0].kids[0]) if len(r) > 0 else ""
        return self.failc[name]

    def init_raise(self, m: Mod, body: list[Node], out: list[Node], top: bool) -> bool:
        # the raise of ImportError (or ModuleNotFoundError) that module m's code reaches for sure at its
        # top level (body, if top), where simplify() leaves it, goes to out; True if it is found
        for i in range(len(body)):
            st = body[i]
            if top:
                self.pos = i
            run: list[Node] = []
            if st.kind == "raise" and len(st.kids) > 0 and import_error(st.kids[0]) != "":
                out.append(st)
                return True
            if (self.static_if(m, st, {}, run) or self.optional(m, st, run, True)) and self.init_raise(m, run, out, False):
                return True
        return False

    def guarded(self) -> None:
        # an optional import is decided at compile time, so the code that runs in its try must not
        # raise ImportError in another way: neither what the modules it imports run at import (and
        # the modules they import) nor the statements after the imports, by a raise of their own or
        # by a call, if a function of the program may raise ImportError. The site (a pass statement
        # where the try was) becomes an error where it is compiled.
        back: dict[str, str] = {}  # what failing() found, by the failing module and the importing one
        for i in range(len(self.sites)):
            s = self.sites[i]
            m = self.sitem[i]
            seen: dict[str, bool] = {}
            why = ""
            for x in s.kids:
                if x.s in self.mods and why == "":
                    why = self.why(self.raises(self.mods[x.s], "", seen), f"the code of module '{x.s}'")
            key = s.s + " " + m.name
            if s.s in self.mods and why == "" and key not in back:
                back[key] = self.failing(self.mods[s.s], m)
            if s.s in self.mods and why == "":
                why = back[key]
            if why == "":
                why = self.why(self.raises_in(self.siterest[i], m, False, seen), "the code that runs in the try")
            s.kids = []
            if why != "":
                s.kind = "badimport"
                s.s = why

    def failing(self, t: Mod, m: Mod) -> str:
        # what keeps an optional import in module m of module t, whose code raises ImportError at its
        # top level, from being decided: t's code may raise it otherwise, or import m back (CPython's
        # import then finds m half run, and succeeds); the message, or ""
        why = self.why(self.raises(t, t.name, {}), f"the code of module '{t.name}', besides its top-level raise,")
        if why == "" and self.imports_mod(t.body, m.name, {}, False):
            return f"module '{t.name}' imports this module as its code runs, before that raises ImportError: an optional import of it here is not supported"
        if why == "" and self.imports_mod(t.body, m.name, {}, True) and self.raises_in(t.body, t, True, {}) > 0:
            return f"module '{t.name}' may import this module as its code runs (through a call), before that raises ImportError: an optional import of it here is not supported"
        return why

    def why(self, r: int, what: str) -> str:
        # the message for code that may raise ImportError (raises_in() found r), or ""
        tail = "which the except clause would catch: not supported (Pystachy decides optional imports at compile time)"
        if r == 2:
            return f"{what} may raise ImportError, {tail}"
        for t in self.order if r == 1 and self.fn == "?" else self.order[:0]:
            if self.fn == "?" or self.fn == "":
                self.fn = self.fn_raises(t, t.body)
        if r == 1 and self.fn != "":
            return f"{what} may raise ImportError through a call (function {self.fn} may raise it), {tail}"
        return ""

    def fn_raises(self, t: Mod, n: Node) -> str:
        # the first function or method in code n of module t that may raise ImportError, by a raise of
        # its own or by an import of a module whose code may: its name, or ""
        for k in n.kids:
            if k.kind == "def" and self.raises_in(k.kids[2], t, False, {}) == 2:
                return f"{t.name + '.' if t.name != '' else ''}{k.s}()"
            r = self.fn_raises(t, k) if k.kind != "def" else ""
            if r != "":
                return r
        return ""

    def raises(self, m: Mod, ok: str, seen: dict[str, bool]) -> int:
        # may module m's code, as it runs at import, raise ImportError (other than the top-level raise
        # of module ok, which an optional import guards)? As raises_in()
        if m.name != ok and m.name in self.rmemo:
            return self.rmemo[m.name]
        if m.name in seen:
            self.rcyc = True  # (its code runs already, or was counted: a result that includes it is not its own)
            return 0
        top = len(seen) == 0  # (then what it finds is all its code may run, cycles or not)
        seen[m.name] = True
        cyc = self.rcyc
        self.rcyc = False
        r = self.raises_in(m.body, m, m.name == ok, seen)
        if m.name != ok and (top or not self.rcyc):
            self.rmemo[m.name] = r
        self.rcyc = self.rcyc or cyc
        return r

    def raises_in(self, n: Node, m: Mod, ok: bool, seen: dict[str, bool]) -> int:
        # may code n of module m raise ImportError as it runs (not the bodies of the functions it
        # defines)? 2 if by a raise of its own or of a module it imports, 1 if it may call a
        # function or method of the program (any call but of a builtin with constant arguments, an
        # operator, a truth test, ...), else 0
        k = n.kind
        if k == "raise" and len(n.kids) > 0 and import_error(n.kids[0]) != "" and not (ok and n.s == "init"):
            return 2
        if k == "call" and self.plain_call(n, m):
            return 0
        if k == "assign" and n.s == "from" and n.kids[-1].kind == "name" and owner(n.kids[-1].s) in self.mods and not self.binds_surely(owner(n.kids[-1].s), short(n.kids[-1].s)):
            return 2  # (from m import x, where m's code may leave x unbound: CPython raises ImportError)
        r = 0 if k in NOCALL else 1
        if k == "uimport":
            for x in n.kids:
                if x.kind == "str" and x.s in self.mods:
                    r = max(r, self.raises(self.mods[x.s], "", seen))
        own = k == "try" and catches_import(n) and not may_end(n, True)  # (a try whose clauses catch ImportError, and do not re-raise it)
        for i in range(len(n.kids)):
            if (k == "def" and (i == 1 or i == 2)) or (k == "annassign" and i == 1) or (k.endswith("param") and i == 0) or (own and i == 0):
                continue  # (a def runs its parameters' defaults and decorators, not its body; annotations call nothing)
            if r < 2:
                r = max(r, self.raises_in(n.kids[i], m, ok, seen))
        return r

    def plain_call(self, n: Node, m: Mod) -> bool:
        # a call of a builtin (that module m does not rebind) with constant arguments: print("loaded")
        f = n.kids[0]
        if f.kind != "name" or f.s not in PYBUILTINS or f.s in m.kinds:
            return False
        for a in n.kids[1:]:
            v = a.kids[0] if a.kind == "kw" else a
            if v.kind != "str" and v.kind != "int" and v.kind != "float" and v.kind != "None" and v.kind != "True" and v.kind != "False":
                return False
        return True

    def imports_mod(self, n: Node, name: str, seen: dict[str, bool], fns: bool) -> bool:
        # does code n import module name, itself or through the modules it imports (with fns, also
        # in the functions they define)?
        if n.kind == "uimport":
            for x in n.kids:
                if x.s == name:
                    return True
                if x.s in self.mods and x.s not in seen:
                    seen[x.s] = True
                    if self.imports_mod(self.mods[x.s].body, name, seen, fns):
                        return True
        for k in n.kids if fns or n.kind != "def" else n.kids[:0]:
            if self.imports_mod(k, name, seen, fns):
                return True
        return False

    def submodules(self) -> None:
        # a package that binds a name x itself (util = "a string") while the program imports its
        # submodule x too: the first import of the submodule rebinds the package's x to it, at a time
        # Pystachy cannot tell, unless the package's own code imports the submodule before it binds x
        # (from .parse import parse). Such an x is ambiguous (Mod.amb): reading it from another module
        # (qmod(), take()) or in the package's functions (qexpr()) is an error where it is compiled
        for t in self.order:
            for x in t.kinds:
                sub = t.name + "." + x
                if t.pdir != "" and sub in self.mods and t.kinds[x] != "m:" + sub and not self.own_first(t, x):
                    t.amb[x] = self.imports_mod(t.body, sub, {}, True)
        for i in range(len(self.taken)):
            n = self.taken[i]
            t = self.mods[n.kids[0].s]
            x = n.kids[1].s
            if n.kind == "takemid" and not (x in t.amb and not t.amb[x] and x not in t.fnglobal):
                # (attribute x of t is the submodule only once an import of it has rebound t's own x,
                # as for the last step, below; else CPython raises ImportError)
                n.kids[2].kind = "badimport"
                n.kids[2].s = self.ambiguous(t.name, x) if x in t.amb else f"import {n.kids[3].s} as {n.s}: '{t.name}.{x}' is the package's own '{x}', not its submodule (not supported: CPython raises ImportError)"
            elif n.kind != "takemid" and x in t.amb:
                # (import t.x as y runs the submodule's code after t's, so t's x is the submodule from
                # then on, unless the submodule's code may run within t's or a function of t rebinds x)
                sure = n.kind == "takesub" and not t.amb[x] and x not in t.fnglobal
                msg = self.ambiguous(t.name, x)
                if len(n.kids) > 2:
                    n.kids[2].kind = "pass" if sure else "badimport"  # (the copy of a variable)
                    n.kids[2].s = msg
                    n.kids[2].kids = []
                self.takek[i][n.s] = "m:" + t.name + "." + x if sure else "x:" + msg
        for i in range(len(self.stars)):
            # from t import * without __all__ binds the public submodules of t that have been imported
            # by then too: one t's own code imports for sure, but another only where its import may
            # have run (an error where it is read)
            t = self.mods[self.stars[i].kids[0].s]
            m = self.starm[i]
            for sub in self.mods:
                x = sub[len(t.name) + 1 :]
                if sub.startswith(t.name + ".") and "." not in x and not x.startswith("_") and x not in t.kinds:
                    msg = f"'from {t.name} import *' binds '{x}' to the submodule '{sub}' only if an import of it has run before, and Pystachy cannot tell whether one has (not supported)"
                    sure = False
                    for st in t.body.kids:
                        for y in st.kids if st.kind == "uimport" else st.kids[:0]:
                            sure = sure or y.s == sub
                    k = m.kinds.get(x, "m:" + sub)
                    if sure and k == "m:" + sub:
                        m.kinds[x] = "m:" + sub
                    elif sure:
                        # (the module binds x itself too)
                        if k == "v":
                            msg = f"'{x}' is bound both as a variable and by an import (not supported)"
                        elif k == "f" or k == "c":
                            msg = f"'{x}' is bound both by an import and by a def or class (not supported)"
                        else:
                            msg = f"'{x}' is bound by two imports, to different modules, functions or classes (not supported)"
                        fail(msg, self.stars[i].line)
                    elif x in m.kinds:
                        fail(msg, self.stars[i].line)
                    else:
                        m.kinds[x] = "x:" + msg

    def own_first(self, t: Mod, x: str) -> bool:
        # does package t's top-level code import its submodule x before anything in it binds x, while
        # no function rebinds x? Then x is t's own binding once t's code has run
        if x in t.fnglobal:
            return False
        for st in t.body.kids:
            for y in st.kids if st.kind == "uimport" else st.kids[:0]:
                if y.s == t.name + "." + x:
                    return True
            names: dict[str, bool] = {}
            binds([st], names, True)
            if x in names:
                return False
        return False

    def ambiguous(self, p: str, x: str) -> str:
        return f"'{p}.{x}' is the package's own '{x}' until the program's first import of its submodule '{p}.{x}' replaces it, and Pystachy cannot tell which of the two this is (not supported)"

    def decide(self, m: Mod, e: Node, scope: dict[str, bool], pre: list[Node]) -> int:
        # an if condition that tests the platform, decided for the POSIX systems Pystachy compiles
        # for (sys.platform == "win32" or "cygwin", ..., sys.platform.startswith("win"), os.name ==
        # "nt", sys.platform in ("win32", ...)), TYPE_CHECKING or an imported module's __name__ ==
        # "__main__" (false), also under not/and/or: 1 or 0, after appending to pre what still runs
        # for the other operands, in CPython's order ("if x: pass" for an operand x that is
        # evaluated and tested); -1 if e is undecided
        if e.kind == "unary" and e.s == "not":
            r = self.decide(m, e.kids[0], scope, pre)
            return 1 - r if r >= 0 else -1
        if e.kind == "boolop":
            stop = 0 if e.s == "and" else 1  # the value that decides e on its own
            a: list[Node] = []
            b: list[Node] = []
            ra = self.decide(m, e.kids[0], scope, a)
            rb = self.decide(m, e.kids[1], scope, b) if ra != stop else -1
            if ra == stop or (ra >= 0 and rb >= 0):
                pre.extend(a)
                pre.extend(b)
                return ra if ra == stop else rb
            if ra < 0 and rb == stop:
                # x and False, x or True: x runs and is tested, then what the right operand runs where x
                # does not decide
                run = mk("block", "", e.line, b if len(b) > 0 else [mk("pass", "", e.line, [])])
                skip = mk("block", "", e.line, [])
                pre.append(mk("if", "", e.line, [e.kids[0], run if stop == 0 else skip, skip if stop == 0 else run]))
                return stop
            return -1
        if e.kind == "attr" and e.s == "TYPE_CHECKING" and e.kids[0].kind == "name" and self.special(m, e.kids[0].s, scope) == "typing":
            return 0
        if e.kind == "name" and self.special(m, e.s, scope) == "typing.TYPE_CHECKING":
            return 0
        if m.name != "" and is_main_guard(e) and "__name__" not in scope and "__name__" not in m.rebound:
            return 0  # (in an imported module)
        other = "win32 cygwin msys nt java emscripten wasi ios android"
        if e.kind == "cmp" and (e.s == "in" or e.s == "not in") and (e.kids[1].kind == "tuple" or e.kids[1].kind == "list") and e.kids[0].kind == "attr" and e.kids[0].s == "platform" and e.kids[0].kids[0].kind == "name" and self.special(m, e.kids[0].kids[0].s, scope) == "sys":
            # sys.platform in ("win32", "cygwin")
            for x in e.kids[1].kids:
                if x.kind != "str" or x.s not in other.split():
                    return -1
            return 0 if e.s == "in" else 1
        if e.kind == "cmp" and (e.s == "==" or e.s == "!=") and e.kids[1].kind == "str" and e.kids[0].kind == "attr" and e.kids[0].kids[0].kind == "name":
            mod = self.special(m, e.kids[0].kids[0].s, scope)
            r = -1
            if mod == "sys" and e.kids[0].s == "platform" and e.kids[1].s in other.split():
                r = 0
            if mod == "os" and e.kids[0].s == "name":
                r = 1 if e.kids[1].s == "posix" else 0
            return r if r < 0 or e.s == "==" else 1 - r
        if e.kind == "call" and len(e.kids) == 2 and e.kids[1].kind == "str" and e.kids[0].kind == "attr" and e.kids[0].s == "startswith":
            pa = e.kids[0].kids[0]
            if pa.kind == "attr" and pa.s == "platform" and pa.kids[0].kind == "name" and self.special(m, pa.kids[0].s, scope) == "sys":
                if e.kids[1].s in "win win32 cygwin msys emscripten wasi java".split():
                    return 0
        return -1

    def special(self, m: Mod, name: str, scope: dict[str, bool]) -> str:
        # what name is in module m's code, where scope (the names of the function or class the code
        # is in) does not hide it, if m binds it only by imports special_import() recognizes, one of
        # them at its top level before the code (self.pos) if that is top-level code: a builtin module
        # (import sys, import os as _os: "sys", "os") or "typing.TYPE_CHECKING"; else "". In a
        # function that binds name only by such imports of its own, what they bind, where one of
        # them has surely run (self.fsure)
        if name in self.fs.spec and name not in self.fs.rebound:
            return self.fs.spec[name] if name in self.fsure else ""
        if name in scope or name in m.rebound or name not in m.specat:
            return ""
        return m.spec[name] if self.pos < 0 or m.specat[name] < self.pos else ""

    def prescan(self, m: Mod) -> None:
        # what simplify() needs to know of m's code first: the names it binds other than by the
        # imports special_import() recognizes (rebound()), and the names those imports bind
        # (Mod.spec). A star import that binds such a name otherwise is an error (bind()).
        m.rebound = rebound(m.body.kids, False)
        specials(m, m.body.kids, -1)

    def imports(self, m: Mod, blk: Node, infn: bool) -> None:
        # load the user modules that the import statements in blk name, and rewrite those
        out: list[Node] = []
        added: list[str] = []  # (what blk surely binds holds only within it)
        for st in blk.kids:
            if st.kind == "import" and infn and m.name != "":
                self.later.append(st)
                self.laterm.append(m)
                self.laterb.append(blk)
                self.laterd.append(self.curdef)
                out.append(st)
            elif st.kind == "import":
                self.import_stmt(m, st, infn, out)
            else:
                out.append(st)
                saved = self.curdef
                if st.kind == "def":
                    self.curdef = str(st.line)
                    self.fks[self.curdef] = {}
                    self.fgl[self.curdef] = {}
                    globals_in(st.kids[2].kids, self.fgl[self.curdef])
                elif not infn and (st.kind == "for" or st.kind == "while"):
                    binds([st], self.maybe, True, m.name if m.pdir != "" else "")  # (an earlier pass of the loop may have run its body)
                intry = self.intry
                optry = self.optry
                self.intry = 0 if st.kind == "def" else intry + 1 if st.kind == "try" else intry
                for kid in st.kids[0].kids if st.kind == "subclass" else st.kids:
                    self.optry = optry and st.kind != "def" or (st.kind == "try" and kid is st.kids[0] and catches_import(st))
                    if kid.kind == "block":
                        self.imports(m, kid, infn or st.kind == "def")
                    elif kid.kind == "except":
                        self.imports(m, kid.kids[1], infn)
                self.intry = intry
                self.optry = optry
                self.curdef = saved
            if not infn:
                binds([st], self.maybe, True, m.name if m.pdir != "" else "", False)  # (imports() did its blocks)
                now: dict[str, bool] = {}
                surely_binds(st, now, self.sure, False)  # (and so an elif chain is not walked again for each elif)
                for nm in now:
                    if nm not in self.sure:
                        self.sure[nm] = True
                        added.append(nm)
        if blk is not m.body:
            for nm in added:
                if nm in self.sure:
                    del self.sure[nm]
        blk.kids = out

    def bind(self, m: Mod, name: str, k: str, infn: bool, line: int) -> None:
        # what an import binds name to; in a function, for that function only. One binding stands for
        # all the code, so a name that an earlier import bound to another module, function or class
        # is an error (in a function, where it is compiled)
        ks = self.fks[self.curdef] if infn else m.kinds
        old = ks.get(name, k)
        if old != k and (old.startswith("m:") or old.startswith("b:") or old.startswith("a:")) and not k.startswith("x:"):
            k = f"x:'{name}' is bound by two imports, to different modules, functions or classes (not supported)"
            if not infn:
                fail(k[2:], line)
        ks[name] = k

    def import_stmt(self, m: Mod, st: Node, infn: bool, out: list[Node]) -> None:
        # one import statement becomes: an import node with its builtin modules (for code
        # generation), a uimport node with the user modules to initialize (each package before
        # its submodules), and for every variable taken with from-import an assignment of its
        # current value, as CPython binds it (marked "from")
        line = st.line
        keep = mk("import", st.s, line, [])
        inits = mk("uimport", "", line, [])
        copies: list[Node] = []
        names: list[str] = []
        for a in st.kids if infn else st.kids[:0]:
            if a.s in self.fgl.get(self.curdef, {}) and (st.s.startswith("from.") or not builtin_module(a.kids[1].s) or m.kinds.get(a.s, "") != "b:" + a.kids[0].s):
                # (CPython binds the module's global, which then names one module or another; but
                # for a builtin module that the module's code has bound it to already)
                out.append(mk("badimport", f"an import of '{a.s}' in a function that declares it global is not supported", line, []))
                return
        for a in st.kids:
            path = a.kids[1].s
            if path == "typing_extensions":
                # the typing backport: its names are typing's (those typing has)
                path = "typing"
                a.kids[1].s = path
                a.kids[0].s = "typing" + a.kids[0].s[17:]
            if st.s.startswith("from."):
                path = self.relative(m, st.s, path, line)
            elif builtin_module(path):
                if not infn and m.kinds.get(a.s, "") == "v":
                    fail(f"'{a.s}' is bound both as a variable and as a function, class or import (not supported)", line)
                if a.s == "*":
                    fail(f"'from {path} import *' is not supported", line)
                self.bind(m, a.s, "b:" + a.kids[0].s, infn, line)
                keep.kids.append(a)
                continue
            if infn and not builtin_module(path) and self.modpath(path) == "":
                # a module that cannot be found, imported by a function: an error only where the
                # function is compiled, as CPython's ImportError comes only where it runs
                msg = f"module '{path}' is not supported: it is not a builtin module and there is no {path[path.rfind('.') + 1 :]}.py on the module path"
                out.append(mk("badimport", msg, line, []))
                self.bind(m, a.s, "x:" + msg, infn, line)
                continue
            src = self.find(path, line)
            self.chain(path, inits)
            if a.s == "":
                # an import that fails in an optional import (optional()): its packages' code runs (and
                # the module's own until its raise, guarded), and it binds nothing
                if len(a.kids) > 2:
                    inits.kids[-1].kind = "guard"
                continue
            if st.s == "" and "." in a.kids[0].s:
                # import a.b.c as x binds x to attribute c of a.b, as from a.b import c as x does: the
                # submodule, unless a.b binds c itself. It takes attribute b of a first, which must be
                # the submodule a.b (checked by submodules() where a binds b itself)
                tgt = a.kids[0].s
                i = tgt.find(".")
                while tgt.find(".", i + 1) >= 0:
                    j = tgt.find(".", i + 1)
                    k = self.mods[tgt[:i]].kinds.get(tgt[i + 1 : j], "")
                    if k != "" and k != "m:" + tgt[:j]:
                        chk = mk("pass", "", line, [])
                        out.append(chk)
                        self.taken.append(mk("takemid", a.s, line, [mk("str", tgt[:i], line, []), mk("str", tgt[i + 1 : j], line, []), chk, mk("str", tgt, line, [])]))
                        self.takek.append(m.kinds)
                    i = j
                n = len(self.taken)
                self.take(m, self.mods[tgt[: tgt.rfind(".")]], tgt[tgt.rfind(".") + 1 :], a.s, infn, keep, inits, copies, line)
                if len(self.taken) > n:
                    self.taken[n].kind = "takesub"  # (this import runs the submodule's code: submodules())
                names.append(a.s)
            elif st.s == "":
                # import a.b.c binds a; import a as x binds x to a
                self.bind(m, a.s, "m:" + a.kids[0].s, infn, line)
                names.append(a.s)
                key = f"{m.name} {self.curdef if infn else ''} {a.s}"
                if self.intry == 0:
                    self.solid[key] = True
                elif key not in self.solid:
                    self.fragile[key] = path
            elif a.s == "*":
                for x in self.public(src):
                    self.take(m, src, x, x, infn, keep, inits, copies, line)
                    names.append(x)
                if src.pdir != "" and not has_all(src.body.kids):
                    self.stars.append(mk("star", "", line, [mk("str", src.name, line, [])]))
                    self.starm.append(m)
            else:
                tgt = a.kids[0].s
                self.take(m, src, tgt[tgt.rfind(".") + 1 :], a.s, infn, keep, inits, copies, line)
                names.append(a.s)
        inits.s = " ".join(names)  # (the names the statement binds, for deftime())
        if len(keep.kids) > 0:
            out.append(keep)
        if len(inits.kids) > 0:
            out.append(inits)
        out.extend(copies)

    def chain(self, path: str, inits: Node) -> None:
        # the modules import path initializes: a, a.b, a.b.c
        i = 0
        while i >= 0:
            i = path.find(".", i + 1)
            p = path[:i] if i >= 0 else path
            inits.kids.append(mk("str", p, inits.line, []))

    def relative(self, m: Mod, s: str, path: str, line: int) -> str:
        # from .x import y in module m: the package m is in (m itself if it is one), one level
        # up per extra dot
        base = m.name if m.pdir != "" else m.name[: m.name.rfind(".")] if "." in m.name else ""
        if m.name == "" or (m.pdir == "" and "." not in m.name):
            fail("attempted relative import with no known parent package", line)
        for _ in range(len(s) - 5):
            if base == "":
                break
            base = base[: base.rfind(".")] if "." in base else ""
        if base == "":
            fail("attempted relative import beyond top-level package", line)
        return base + "." + path if path != "" else base

    def public(self, src: Mod) -> list[str]:
        # the names from src import * takes: those __all__ lists, else the names not starting with _
        out: list[str] = []
        found = False
        for st in src.body.kids:
            if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s == "__all__":
                found = True
                out = []
                self.all_names(src, st.kids[1], out)
            elif st.kind == "augassign" and st.s == "+" and st.kids[0].kind == "name" and st.kids[0].s == "__all__":
                self.all_names(src, st.kids[1], out)
            elif st.kind == "expr" and st.kids[0].kind == "call" and st.kids[0].kids[0].kind == "attr" and st.kids[0].kids[0].kids[0].kind == "name" and st.kids[0].kids[0].kids[0].s == "__all__":
                f = st.kids[0].kids[0].s
                args = st.kids[0].kids[1:]
                if f == "append" and len(args) == 1 and args[0].kind == "str":
                    out.append(args[0].s)
                elif f == "extend" and len(args) == 1:
                    self.all_names(src, args[0], out)
                else:
                    fail(f"from {src.name} import *: __all__.{f}() is not supported (only assigning, +=, append and extend)", st.line)
        if found:
            return out
        dels: dict[str, bool] = {}
        deleted(src.body.kids, dels)
        for nm in src.kinds:
            if not nm.startswith("_") and nm not in dels and nm not in src.fnonly:
                out.append(nm)
        return out

    def all_names(self, src: Mod, v: Node, out: list[str]) -> None:
        # the strings of a list or tuple literal assigned to or added to __all__ (or a + of those)
        if v.kind == "binop" and v.s == "+":
            self.all_names(src, v.kids[0], out)
            self.all_names(src, v.kids[1], out)
        elif v.kind == "list" or v.kind == "tuple":
            for x in v.kids:
                if x.kind != "str":
                    fail(f"from {src.name} import *: __all__ must list strings", x.line)
                out.append(x.s)
        else:
            fail(f"from {src.name} import *: __all__ must be a list or tuple of strings", v.line)

    def take(self, m: Mod, src: Mod, x: str, name: str, infn: bool, keep: Node, inits: Node, copies: list[Node], line: int) -> None:
        # from src import x as name
        k = src.kinds.get(x, "")
        if src.name == m.name and not infn and x not in self.sure:
            # (from . import x in a package's own code takes the package's x if its code has bound x
            # by then, else the submodule)
            if x in self.maybe or "*" in self.maybe or x in m.fnglobal:
                fail(f"'{x}' is the package's own '{x}' if its code has bound it before this import, else the submodule '{m.name}.{x}', and Pystachy cannot tell which (not supported)", line)
            k = ""
        if not infn and (m.kinds.get(name, "") == "f" or m.kinds.get(name, "") == "c"):
            fail(f"'{name}' is bound both by an import and by a def or class (not supported)", line)
        if not infn and m.kinds.get(name, "") == "v" and k != "v" and (k != "" or src.pdir != ""):
            fail(f"'{name}' is bound both as a variable and by an import (not supported)", line)
        if k == "" and src.pdir != "":
            # a submodule of the package
            sub = src.name + "." + x
            self.find(sub, line)
            inits.kids.append(mk("str", sub, line, []))
            self.bind(m, name, "m:" + sub, infn, line)
        elif k == "":
            fail(f"cannot import name '{x}' from '{src.name}'", line)
        elif k == "f" or k == "c":
            self.bind(m, name, "a:" + src.q + x, infn, line)
        elif k.startswith("b:"):
            p = k[2:]
            self.bind(m, name, k, infn, line)
            keep.kids.append(mk("alias", name, line, [mk("str", p, line, []), mk("str", p[: p.find(".")] if "." in p else p, line, [])]))
        elif k != "v":
            self.bind(m, name, k, infn, line)
        else:
            if not infn:
                m.kinds[name] = "v"
            copies.append(mk("assign", "from", line, [mk("name", name, line, []), mk("name", src.q + x, line, [])]))
        if src.pdir != "" and k != "" and k != "m:" + src.name + "." + x:
            # the package binds x itself, which an import of its submodule x may rebind (submodules())
            self.taken.append(mk("take", name, line, [mk("str", src.name, line, []), mk("str", x, line, [])] + (copies[-1:] if k == "v" else copies[:0])))
            self.takek.append(self.fks[self.curdef] if infn else m.kinds)

    # ---- qualification of names
    def kind(self, m: Mod, s: str) -> str:
        # what s is bound to in m, where an import in the function being qualified comes first
        return self.fk[s] if s in self.fk else m.kinds.get(s, "")

    def qname(self, m: Mod, s: str, loc: dict[str, bool]) -> str:
        if s in loc or "$" in s:
            return s
        k = self.kind(m, s)
        if k == "f" or k == "c" or k == "v" or k.startswith("b:"):
            if m.name == "" and s in PYBUILTINS:
                return "__main__$" + s  # (other modules' code still sees the builtin)
            return m.q + s
        if k.startswith("a:"):
            return k[2:]
        if k == "" and m.name != "" and s not in PYBUILTINS and not s.startswith("__"):
            return m.q + s  # not defined (the main program's names are not a module's)
        return s

    def qmod(self, m: Mod, n: Node, loc: dict[str, bool]) -> str:
        # the module n denotes (a name bound to one, or a submodule attribute of one), or "";
        # an attribute of a module that is not a module is rewritten to its qualified name
        if n.kind == "name":
            k = self.kind(m, n.s) if n.s not in loc else ""
            return k[2:] if k.startswith("m:") else ""
        if n.kind != "attr":
            return ""
        base = self.qmod(m, n.kids[0], loc)
        if base == "":
            return ""
        if n.s == "__name__":
            n.kind = "str"
            n.s = base
            n.kids = []
            return ""
        t = self.mods[base]
        k = t.kinds.get(n.s, "")
        if n.s in t.amb:
            k = "x:" + self.ambiguous(base, n.s)
        if k.startswith("m:"):
            return k[2:]
        if k == "" and base + "." + n.s in self.mods:
            return base + "." + n.s  # a submodule (unless the package binds the name itself)
        if k == "":
            n.kind = "badattr"
            n.s = f"module attribute '{n.s}' is not supported" if n.s in (MODDUNDERS + " __dict__ __cached__").split() or (n.s == "__path__" and t.pdir != "") else f"module '{base}' has no attribute '{n.s}'"
        elif k.startswith("x:"):
            n.kind = "badattr"
            n.s = k[2:]
        else:
            n.kind = "name"
            n.s = self.qname(t, n.s, {})
        n.kids = []
        return ""

    def qexpr(self, m: Mod, n: Node, loc: dict[str, bool]) -> None:
        k = n.kind
        if k == "name" or k == "attr":
            if k == "name" and n.s == "__name__" and m.name != "" and n.s not in loc:
                if "__name__" in m.rebound:
                    fail(f"module '{m.name}' binds __name__, which is not supported in an imported module", n.line)
                n.kind = "str"
                n.s = m.name
                return
            if k == "name" and n.s == "__debug__":
                n.kind = "True"  # (CPython runs without -O; nothing can bind __debug__)
                return
            root = n
            while root.kind == "attr":
                root = root.kids[0]
            fr = ""
            if k == "attr" and root.kind == "name" and root.s not in loc:
                inf = root.s in self.fk
                key = f"{m.name} {self.fkey if inf else ''} {root.s}"
                if key in self.fragile:
                    fr = f"{self.fragile[key]} {root.s} {'L' if inf else 'G'}"
            mod = self.qmod(m, n, loc)
            if fr != "" and (n.kind == "name" or n.kind == "str"):
                n.mchk = fr
            if mod != "":
                n.kind = "badattr"
                n.s = f"module '{mod}' cannot be used as a value"
                n.kids = []
            elif n.kind == "name" and n.s not in loc and self.kind(m, n.s).startswith("x:"):
                n.kind = "badattr"
                n.s = self.kind(m, n.s)[2:]
            elif n.kind == "name" and n.s not in loc and n.s not in self.fk and n.s in m.amb and (self.qdef or m.amb[n.s]):
                # a package's own name that an import of its submodule may have rebound (submodules())
                n.kind = "badattr"
                n.s = self.ambiguous(m.name, n.s)
            elif n.kind == "name":
                n.s = self.qname(m, n.s, loc)
            elif n.kind == "attr":
                self.qexpr(m, n.kids[0], loc)
        elif k == "listcomp":
            # [element for target in iterable if condition]: the target's names are the comprehension's
            # (added to loc while the rest is qualified, not to a copy: loc has all of a function's locals)
            self.qexpr(m, n.kids[2], loc)
            names: list[str] = []
            names_in(n.kids[1], names)
            added: list[str] = []
            for nm in names:
                if nm not in loc:
                    loc[nm] = True
                    added.append(nm)
            for i in range(len(n.kids)):
                if i != 2:
                    self.qexpr(m, n.kids[i], loc)
            for nm in added:
                del loc[nm]
        else:
            for kid in n.kids:
                self.qexpr(m, kid, loc)

    def qstore(self, m: Mod, t: Node, loc: dict[str, bool]) -> None:
        # an assignment target: a package's own name that an import of its submodule may rebind
        # (Mod.amb) cannot be assigned from another module, as which of the two it replaces is not known
        if t.kind == "tuple" or t.kind == "list":
            for x in t.kids:
                self.qstore(m, x, loc)
            return
        b = self.modof(m, t.kids[0], loc) if t.kind == "attr" else ""
        if b != "" and t.s in self.mods[b].amb:
            t.kind = "badattr"
            t.s = f"assigning '{b}.{t.s}' is not supported: the program's first import of the submodule '{b}.{t.s}' binds it too"
            t.kids = []
        self.qexpr(m, t, loc)

    def modof(self, m: Mod, n: Node, loc: dict[str, bool]) -> str:
        # the module n denotes, as qmod() finds it but without rewriting n, or ""
        if n.kind == "name":
            k = self.kind(m, n.s) if n.s not in loc else ""
            return k[2:] if k.startswith("m:") else ""
        base = self.modof(m, n.kids[0], loc) if n.kind == "attr" else ""
        if base == "" or n.s in self.mods[base].amb:
            return ""
        k = self.mods[base].kinds.get(n.s, "")
        if k.startswith("m:"):
            return k[2:]
        return base + "." + n.s if k == "" and base + "." + n.s in self.mods else ""

    def qann(self, m: Mod, n: Node, loc: dict[str, bool]) -> None:
        # an annotation; a string one (a forward reference), also inside list["Node"], is parsed
        # to qualify the names in it
        if n.kind == "str":
            e = Parser(Lexer(n.s, n.line).run()).test()
            n.kind = e.kind
            n.s = e.s
            n.kids = e.kids
        if n.kind == "index" or n.kind == "tuple" or (n.kind == "binop" and n.s == "|"):
            for k in n.kids:
                self.qann(m, k, loc)
        else:
            self.qexpr(m, n, loc)
            if n.chk and n.kind == "badattr" and " has no attribute " in n.s:
                fail(n.s, n.line)  # (an evaluated annotation: see Loader.reads)

    def qdeco(self, m: Mod, d: Node, loc: dict[str, bool]) -> None:
        # a decorator: the first name of its dotted name (unless it surely names a builtin
        # there: deftime), and the arguments of a call
        root = d.s[: d.s.find(".")] if "." in d.s else d.s
        alias = root not in loc and self.kind(m, root).startswith("a:")  # (shown as written: m$root)
        d.s = (root if d.line in self.bdecos else m.q + root if alias else self.qname(m, root, loc)) + d.s[len(root) :]
        for c in d.kids:
            for a in c.kids[1:]:
                self.qexpr(m, a, loc)

    def qstmts(self, m: Mod, body: list[Node], loc: dict[str, bool], cls: bool) -> None:
        for st in body:
            k = st.kind
            if k == "def":
                if not cls:
                    st.s = self.qname(m, st.s, loc)
                for d in st.kids[3:]:
                    if d.s != "async":
                        self.qdeco(m, d, loc)
                for p in st.kids[0].kids:
                    self.qann(m, p.kids[0], loc)
                    self.qexpr(m, p.kids[1], loc)
                self.qann(m, st.kids[1], loc)
                inner: dict[str, bool] = {}
                for p in st.kids[0].kids:
                    inner[p.s] = True
                local_names(st.kids[2].kids, inner)
                decl: dict[str, bool] = {}
                globals_in(st.kids[2].kids, decl)
                for nm in decl:
                    if nm in inner:
                        del inner[nm]
                saved = self.fk
                key = self.fkey
                indef = self.qdef
                self.fk = self.fks.get(str(st.line), {})
                for nm in self.unsure.get(str(st.line), {}):
                    k = self.fk.get(nm, "")
                    if k.startswith("m:") or k.startswith("a:") or k.startswith("b:"):
                        # (a function's import of a Python module binds a local, which CPython reads
                        # unbound before it runs)
                        st.kids[2].kids.insert(0, mk("badimport", f"'{nm}' is read in {st.s}() where Pystachy cannot tell that the import in it that binds '{nm}' has run (where it has not, CPython raises UnboundLocalError): not supported", st.line, []))
                        break
                self.fkey = str(st.line)
                self.qdef = True
                self.qstmts(m, st.kids[2].kids, inner, False)
                self.qdef = indef
                self.fk = saved
                if cls:
                    loc[st.s] = True
                self.fkey = key
            elif k == "subclass":
                # (a generic class's type parameters stay unqualified in its bases and body)
                tps = dict(loc)
                for nm in st.kids[1].s.split() if st.kids[1].kind == "typeparams" else []:
                    tps[nm] = True
                self.qstmts(m, [st.kids[0]], tps, cls)
                st.s = st.kids[0].s
                for kid in st.kids[1:]:
                    self.qexpr(m, kid, tps)
                if cls:
                    loc[short(st.s)] = True
            elif k == "class":
                # (a class body's own names, in loc once bound, stay unqualified where it reads them)
                st.s = self.qname(m, st.s, loc)
                for d in st.kids[1:]:
                    self.qdeco(m, d, loc)
                self.qstmts(m, st.kids[0].kids, {} if cls else dict(loc), True)  # (class scopes do not nest)
                if cls:
                    loc[short(st.s)] = True
            elif cls and k == "assign":
                # a class attribute: the names it binds are the class's
                self.qexpr(m, st.kids[-1], loc)
                for kid in st.kids[:-1]:
                    if kid.kind != "name" and kid.kind != "tuple":
                        self.qexpr(m, kid, loc)
                collect([st], loc)
            elif cls and k == "annassign" and st.kids[0].kind == "name":
                # a field: the name is the class's, the annotation and default value the module's
                self.qann(m, st.kids[1], loc)
                for kid in st.kids[2:]:
                    self.qexpr(m, kid, loc)
                if len(st.kids) == 3:
                    loc[st.kids[0].s] = True
            elif k == "annassign":
                self.qstore(m, st.kids[0], loc)
                self.qann(m, st.kids[1], loc)
                for kid in st.kids[2:]:
                    self.qexpr(m, kid, loc)
            elif k == "assign":
                for kid in st.kids[:-1]:
                    self.qstore(m, kid, loc)
                self.qexpr(m, st.kids[-1], loc)
            elif k == "import" or k == "global":
                for a in st.kids:
                    a.s = self.qname(m, a.s, {})
            elif k != "uimport":
                for kid in st.kids:
                    if kid.kind == "block":
                        self.qstmts(m, kid.kids, loc, cls)
                    elif kid.kind == "except":
                        # except E as e: E is read, and e bound, like any other name
                        self.qexpr(m, kid.kids[0], loc)
                        if kid.s != "":
                            kid.s = self.qname(m, kid.s, loc)
                        self.qstmts(m, kid.kids[1].kids, loc, cls)
                    else:
                        self.qexpr(m, kid, loc)


# ---------------------------------------------------------------- types
# A type is a canonical string: int float bool str None file, list[T], dict[K,V],
# tuple[A,B], or a class name. LLVM view: i64, double, i1, void, everything else ptr.
HEX = "0123456789ABCDEF"
# the type of a local that only None has been assigned so far (see none_type): a pointer, which
# only comparisons with None may read until a binding of another value types it
NONEVAR = "opt[None]"
IOPS: dict[str, str] = {"&": "and", "|": "or", "^": "xor"}
CHECKED: dict[str, str] = {"+": "sadd", "-": "ssub", "*": "smul"}  # llvm.*.with.overflow
IRT: dict[str, str] = {"//": "pys_floordiv", "%": "pys_mod", "**": "pys_pow", "<<": "pys_shl", ">>": "pys_shr"}
FOPS: dict[str, str] = {"+": "fadd", "-": "fsub", "*": "fmul"}
FRT: dict[str, str] = {"/": "pys_fdiv", "//": "pys_ffloordiv", "%": "pys_fmod", "**": "pys_fpow"}
ICMP: dict[str, str] = {"==": "eq", "!=": "ne", "<": "slt", "<=": "sle", ">": "sgt", ">=": "sge"}
FCMP: dict[str, str] = {"==": "oeq", "!=": "une", "<": "olt", "<=": "ole", ">": "ogt", ">=": "oge"}
# special methods: "number of parameters (with self):required return type"
SPECIAL: dict[str, str] = {"__str__": "1:str", "__repr__": "1:str", "__len__": "1:int", "__bool__": "1:bool", "__format__": "2:str",
                           "__eq__": "2:bool", "__ne__": "2:bool", "__lt__": "2:bool", "__le__": "2:bool", "__gt__": "2:bool", "__ge__": "2:bool"}
for _k in "add sub mul truediv floordiv mod iadd isub imul itruediv ifloordiv imod".split():
    SPECIAL[f"__{_k}__"] = "2:"
# a comparison from pys_cmp_if's result R (-1, 0, 1, or 2 when a NaN makes it unordered)
MIXCMP: dict[str, str] = {"==": "icmp eq i64 R, 0", "!=": "icmp ne i64 R, 0", "<": "icmp eq i64 R, -1", "<=": "icmp sle i64 R, 0",
                          ">": "icmp eq i64 R, 1", ">=": "icmp ule i64 R, 1"}
REFL: dict[str, str] = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}  # a < b may run b.__gt__(a)
ORDOP: dict[str, int] = {"<": 0, "<=": 1, ">": 2, ">=": 3}  # op codes shared with runtime.c
DUNDER: dict[str, str] = {"+": "__add__", "-": "__sub__", "*": "__mul__", "/": "__truediv__", "//": "__floordiv__", "%": "__mod__",
                          "==": "__eq__", "!=": "__ne__", "<": "__lt__", "<=": "__le__", ">": "__gt__", ">=": "__ge__"}
# builtin and module functions that are one runtime call: "name(argtypes)": "C function:result type"
CALLS: dict[str, str] = {
    "ord(str)": "pys_ord:int", "chr(int)": "pys_chr:str", "int(float)": "pys_f2i:int", "int(str,int)": "pys_int_str:int",
    "float(str)": "pys_float_str:float", "round(float)": "pys_round:int", "round(float,int)": "pys_round_n:float", "input(str)": "pys_input:str",
    "abs(float)": "fabs:float", "list(str)": "pys_str_list:list[str]",
    "sum(list[int],int)": "pys_sum_int:int", "sum(list[float],float)": "pys_sum_float:float", "sum(list[bool],int)": "pys_sum_int:int",
    "sum(list[float],int)": "pys_sum_float_int:float", "sum(list[int],float)": "pys_sum_int_float:float",
    "sum(list[bool],float)": "pys_sum_int_float:float", "any(list[bool])": "pys_any:bool",
    "all(list[bool])": "pys_all:bool", "any(list[int])": "pys_any:bool", "all(list[int])": "pys_all:bool",
    "os.system(str)": "pys_system:int", "os.execv(str,list[str])": "pys_execv:None",
    "os.getpid()": "pys_getpid:int", "os.path.exists(str)": "pys_exists:bool", "os.path.realpath(str)": "pys_realpath:str",
    "os.getenv(str,str)": "pys_getenv:str",
    "os.remove(str)": "pys_remove:None", "os.rmdir(str)": "pys_rmdir:None", "tempfile.mkdtemp()": "pys_mkdtemp:str",
    "math.floor(float)": "pys_floor:int", "math.ceil(float)": "pys_ceil:int", "math.trunc(float)": "pys_m_trunc:int",
    "math.gcd(int,int)": "pys_m_gcd:int", "math.lcm(int,int)": "pys_m_lcm:int", "math.isqrt(int)": "pys_m_isqrt:int",
    "math.factorial(int)": "pys_m_factorial:int", "math.comb(int,int)": "pys_m_comb:int", "math.perm(int,int)": "pys_m_perm:int",
    "math.isfinite(float)": "pys_m_isfinite:bool", "math.isinf(float)": "pys_m_isinf:bool", "math.isnan(float)": "pys_m_isnan:bool",
    "math.log(float,float)": "pys_m_logb:float",
    "time.time()": "pys_time:float", "time.time_ns()": "pys_time_ns:int", "time.monotonic()": "pys_monotonic:float",
    "time.monotonic_ns()": "pys_monotonic_ns:int", "time.perf_counter()": "pys_monotonic:float",
    "time.perf_counter_ns()": "pys_monotonic_ns:int", "time.process_time()": "pys_process_time:float",
    "time.process_time_ns()": "pys_process_time_ns:int", "time.sleep(float)": "pys_sleep:None", "time.sleep(int)": "pys_sleep_int:None",
    "time.sleep(bool)": "pys_sleep_int:None", "sys.setrecursionlimit(int)": "pys_setrecursionlimit:None",
    "sys.setrecursionlimit(bool)": "pys_setrecursionlimit:None", "sys.getrecursionlimit()": "pys_getrecursionlimit:int",
}
# the errno module: the platform's error numbers (runtime.c's table)
ERRNO: dict[str, bool] = {}
for _k in ("EPERM ENOENT ESRCH EINTR EIO ENXIO E2BIG ENOEXEC EBADF ECHILD EAGAIN ENOMEM EACCES EFAULT ENOTBLK EBUSY EEXIST EXDEV ENODEV "
           "ENOTDIR EISDIR EINVAL ENFILE EMFILE ENOTTY ETXTBSY EFBIG ENOSPC ESPIPE EROFS EMLINK EPIPE EDOM ERANGE EDEADLK ENAMETOOLONG "
           "ENOLCK ENOSYS ENOTEMPTY ELOOP EWOULDBLOCK ENOMSG EIDRM ENOSTR ENODATA ETIME ENOSR EREMOTE ENOLINK EPROTO EMULTIHOP EBADMSG "
           "EOVERFLOW EILSEQ EUSERS ENOTSOCK EDESTADDRREQ EMSGSIZE EPROTOTYPE ENOPROTOOPT EPROTONOSUPPORT ESOCKTNOSUPPORT EOPNOTSUPP "
           "ENOTSUP EPFNOSUPPORT EAFNOSUPPORT EADDRINUSE EADDRNOTAVAIL ENETDOWN ENETUNREACH ENETRESET ECONNABORTED ECONNRESET ENOBUFS "
           "EISCONN ENOTCONN ESHUTDOWN ETOOMANYREFS ETIMEDOUT ECONNREFUSED EHOSTDOWN EHOSTUNREACH EALREADY EINPROGRESS ESTALE EDQUOT "
           "ECANCELED EOWNERDEAD ENOTRECOVERABLE").split():
    ERRNO[_k] = True
# math functions raise CPython's domain and range errors (runtime.c, pys_m_*)
for _k in "sqrt sin cos tan asin acos atan sinh cosh tanh exp log log2 log10 fabs log1p expm1 exp2 cbrt degrees radians asinh acosh atanh erf erfc ulp".split():
    CALLS[f"math.{_k}(float)"] = f"pys_m_{_k}:float"
for _k in "pow atan2 hypot fmod copysign nextafter remainder".split():
    CALLS[f"math.{_k}(float,float)"] = f"pys_m_{_k}:float"
CALLS["math.fma(float,float,float)"] = "pys_m_fma:float"
CALLS["math.ldexp(float,int)"] = "pys_m_ldexp:float"
CALLS["math.frexp(float)"] = "pys_m_frexp:tuple[float,int]"
CALLS["math.modf(float)"] = "pys_m_modf:tuple[float,float]"
# the modules a program may import; their functions and attributes are the CALLS entries and modattr()
MODULES: dict[str, bool] = {}
for _k in "sys os os.path math tempfile typing dataclasses __future__ builtins time errno".split():
    MODULES[_k] = True
MODATTRS: dict[str, bool] = {}
for _k in ("sys.argv sys.maxsize sys.stdin sys.stdout sys.stderr sys.platform math.pi math.e math.inf math.tau math.nan "
           "os.name os.sep os.curdir os.pardir os.extsep os.pathsep os.linesep os.devnull").split():
    MODATTRS[_k] = True
# the os module's constants on POSIX systems
OSCONST: dict[str, str] = {"os.name": "posix", "os.sep": "/", "os.curdir": ".", "os.pardir": "..", "os.extsep": ".",
                           "os.pathsep": ":", "os.linesep": "\n", "os.devnull": "/dev/null"}
TYPING: dict[str, bool] = {}
for _k in ("List Dict Tuple Optional TextIO Any Union Callable Set FrozenSet Iterable Iterator Sequence Mapping Final ClassVar NamedTuple "
           "TypeVar Generic cast IO BinaryIO AnyStr Literal Protocol TYPE_CHECKING overload NoReturn Never Self TypeAlias ParamSpec "
           "Concatenate TypeGuard Annotated Awaitable Coroutine AsyncIterator AsyncIterable Generator Type DefaultDict OrderedDict "
           "Counter Deque ChainMap Hashable Sized Collection Container Reversible MutableMapping MutableSequence MutableSet "
           "AbstractSet KeysView ItemsView ValuesView SupportsInt SupportsFloat SupportsIndex SupportsAbs SupportsRound TypedDict "
           "LiteralString Required NotRequired Unpack TypeVarTuple override final get_type_hints no_type_check runtime_checkable "
           "NewType assert_never reveal_type dataclass_transform Pattern Match Text ByteString AsyncContextManager AsyncGenerator "
           "ContextManager ForwardRef MappingView NoDefault ParamSpecArgs ParamSpecKwargs ReadOnly SupportsBytes SupportsComplex "
           "TypeAliasType TypeIs assert_type clear_overloads get_args get_origin get_overloads get_protocol_members is_protocol "
           "is_typeddict no_type_check_decorator").split():
    TYPING[_k] = True
# collections.abc: imported as typing's names are (Mapping[K, V] is dict[K, V], see typeof)
ABCS: dict[str, bool] = {}
for _k in ("Awaitable Coroutine AsyncIterable AsyncIterator AsyncGenerator Hashable Iterable Iterator Generator Reversible Sized "
           "Container Callable Collection Set MutableSet Mapping MutableMapping MappingView KeysView ItemsView ValuesView Sequence "
           "MutableSequence ByteString Buffer").split():
    ABCS[_k] = True
CLASSVAR = "typing.ClassVar (a class attribute) is not supported"
OPTTYPES = "class types, str, int, float, bool, list, dict and tuple"
TYPEVAR = " is only supported in the annotations of a module-level function's parameters and return, which make the function a template"
STUB = "an @overload stub of 'NAME' must be followed by the def that implements it (calling a stub raises NotImplementedError)"
PATHLIKE = "os.PathLike is only supported in a union with str (str | os.PathLike[str] is a str: Pystachy has no other path type)"
FUTURE: dict[str, bool] = {}
for _k in "annotations division absolute_import print_function generators nested_scopes with_statement unicode_literals generator_stop".split():
    FUTURE[_k] = True
# omitted arguments, as source text: f() -> f(default), f(x) -> f(x, default)
DEFAULTS: dict[str, str] = {"int": "0", "float": "0.0", "str": '""', "bool": "False",
                            "list": "[]", "dict": "{}", "int(str)": "10", "sum(list[int])": "0",
                            "sum(list[float])": "0.0", "sum(list[bool])": "0"}
# the builtin exceptions raise accepts; "x": special arguments, so at most one is supported;
# "-": arguments that cannot be given here
EXCEPTIONS: dict[str, str] = {}
for _k in ("BaseException GeneratorExit KeyboardInterrupt SystemExit Exception ArithmeticError FloatingPointError OverflowError "
           "ZeroDivisionError AssertionError AttributeError BufferError EOFError ImportError ModuleNotFoundError LookupError "
           "IndexError KeyError MemoryError NameError UnboundLocalError ReferenceError RuntimeError NotImplementedError "
           "RecursionError PythonFinalizationError StopAsyncIteration StopIteration SystemError TypeError ValueError "
           "UnicodeError Warning BytesWarning DeprecationWarning EncodingWarning FutureWarning ImportWarning "
           "PendingDeprecationWarning ResourceWarning RuntimeWarning SyntaxWarning UnicodeWarning UserWarning").split():
    EXCEPTIONS[_k] = ""
for _k in ("OSError IOError EnvironmentError BlockingIOError ChildProcessError ConnectionError BrokenPipeError "
           "ConnectionAbortedError ConnectionRefusedError ConnectionResetError FileExistsError FileNotFoundError "
           "InterruptedError IsADirectoryError NotADirectoryError PermissionError ProcessLookupError TimeoutError "
           "SyntaxError IndentationError TabError").split():
    EXCEPTIONS[_k] = "x"
for _k in "UnicodeDecodeError UnicodeEncodeError UnicodeTranslateError ExceptionGroup BaseExceptionGroup".split():
    EXCEPTIONS[_k] = "-"
# the builtin exception classes, each with its bases (CPython 3.13's: tools/check_runtime.py
# checks them), and io.UnsupportedOperation, which the runtime raises too. IOError and
# EnvironmentError are other names of OSError. An except clause catches a class and the classes
# deriving from it
EXCBASES: dict[str, str] = {"BaseException": ""}
for _k in ("BaseExceptionGroup:BaseException GeneratorExit:BaseException KeyboardInterrupt:BaseException SystemExit:BaseException "
           "Exception:BaseException ArithmeticError:Exception FloatingPointError:ArithmeticError OverflowError:ArithmeticError "
           "ZeroDivisionError:ArithmeticError AssertionError:Exception AttributeError:Exception BufferError:Exception "
           "EOFError:Exception ExceptionGroup:BaseExceptionGroup,Exception ImportError:Exception ModuleNotFoundError:ImportError "
           "LookupError:Exception IndexError:LookupError KeyError:LookupError MemoryError:Exception NameError:Exception "
           "UnboundLocalError:NameError OSError:Exception BlockingIOError:OSError ChildProcessError:OSError ConnectionError:OSError "
           "BrokenPipeError:ConnectionError ConnectionAbortedError:ConnectionError ConnectionRefusedError:ConnectionError "
           "ConnectionResetError:ConnectionError FileExistsError:OSError FileNotFoundError:OSError InterruptedError:OSError "
           "IsADirectoryError:OSError NotADirectoryError:OSError PermissionError:OSError ProcessLookupError:OSError "
           "TimeoutError:OSError ReferenceError:Exception RuntimeError:Exception NotImplementedError:RuntimeError "
           "PythonFinalizationError:RuntimeError RecursionError:RuntimeError StopAsyncIteration:Exception StopIteration:Exception "
           "SyntaxError:Exception IndentationError:SyntaxError TabError:IndentationError SystemError:Exception TypeError:Exception "
           "ValueError:Exception UnicodeError:ValueError UnicodeDecodeError:UnicodeError UnicodeEncodeError:UnicodeError "
           "UnicodeTranslateError:UnicodeError Warning:Exception BytesWarning:Warning DeprecationWarning:Warning "
           "EncodingWarning:Warning FutureWarning:Warning ImportWarning:Warning PendingDeprecationWarning:Warning "
           "ResourceWarning:Warning RuntimeWarning:Warning SyntaxWarning:Warning UnicodeWarning:Warning UserWarning:Warning "
           "io.UnsupportedOperation:OSError,ValueError").split():
    EXCBASES[_k[: _k.find(":")]] = _k[_k.find(":") + 1 :]


# the hidden fields an exception class's objects begin with (see Gen.declare_fields), with their types
EXCFIELDS = "cls:str str:str args:str code:int hc:bool"
# the attributes of builtin exception classes that their str(), repr() or exit status read: an
# exception class's field of that name would be theirs (not supported)
EXCATTRS: dict[str, str] = {"BaseException": "args", "SystemExit": "code", "OSError": "errno strerror filename filename2", "ImportError": "msg"}
# the attributes that the __init__ of builtin exception classes sets (StopIteration's value to its
# first argument, the others to their keyword argument or None), which only CPython reads: an
# exception class's field of that name must be assigned after that __init__ runs
EXCINIT: dict[str, str] = {"StopIteration": "value", "AttributeError": "name obj", "NameError": "name", "ImportError": "name path"}


def is_excname(s: str) -> bool:
    # does s name a builtin exception class (OSError's other names too)
    return s in EXCBASES or s == "IOError" or s == "EnvironmentError"


# the keyword arguments that the __init__ of builtin exception classes takes (and those deriving from them)
EXCKW: dict[str, str] = {"ImportError": "name path", "AttributeError": "name obj", "NameError": "name"}


def exc_base_of(c: str, base: str) -> bool:
    # is c, which may name a builtin exception class (OSError's other names too), base or derived from it
    c = "OSError" if c == "IOError" or c == "EnvironmentError" else c
    return c in EXCBASES and exc_derives(c, base)


def exc_derives(c: str, base: str) -> bool:
    # is exception class c base, or derived from it (EXCBASES)
    if c == base:
        return True
    for b in EXCBASES[c].split(","):
        if b != "" and exc_derives(b, base):
            return True
    return False


# the attributes hasattr() finds on values of the builtin types ("seq": str, list, tuple, dict), and
# on every value; other attribute names are not decided
HASATTR: dict[str, str] = {
    "any": "__class__ __delattr__ __dir__ __doc__ __eq__ __format__ __ge__ __getattribute__ __getstate__ __gt__ __hash__ __init__ "
           "__init_subclass__ __le__ __lt__ __ne__ __new__ __reduce__ __reduce_ex__ __repr__ __setattr__ __sizeof__ __str__ __subclasshook__",
    "obj": "__dict__ __firstlineno__ __module__ __static_attributes__ __weakref__",
    "int": "__abs__ __add__ __and__ __bool__ __ceil__ __divmod__ __float__ __floor__ __floordiv__ __getnewargs__ __index__ __int__ "
           "__invert__ __lshift__ __mod__ __mul__ __neg__ __or__ __pos__ __pow__ __radd__ __rand__ __rdivmod__ __rfloordiv__ "
           "__rlshift__ __rmod__ __rmul__ __ror__ __round__ __rpow__ __rrshift__ __rshift__ __rsub__ __rtruediv__ __rxor__ __sub__ "
           "__truediv__ __trunc__ __xor__ as_integer_ratio bit_count bit_length conjugate denominator from_bytes imag is_integer "
           "numerator real to_bytes",
    "float": "__abs__ __add__ __bool__ __ceil__ __divmod__ __float__ __floor__ __floordiv__ __getformat__ __getnewargs__ __int__ "
             "__mod__ __mul__ __neg__ __pos__ __pow__ __radd__ __rdivmod__ __rfloordiv__ __rmod__ __rmul__ __round__ __rpow__ "
             "__rsub__ __rtruediv__ __sub__ __truediv__ __trunc__ as_integer_ratio conjugate fromhex hex imag is_integer real",
    "str": "__add__ __contains__ __getitem__ __getnewargs__ __iter__ __len__ __mod__ __mul__ __rmod__ __rmul__ capitalize casefold "
           "center count encode endswith expandtabs find format format_map index isalnum isalpha isascii isdecimal isdigit "
           "isidentifier islower isnumeric isprintable isspace istitle isupper join ljust lower lstrip maketrans partition "
           "removeprefix removesuffix replace rfind rindex rjust rpartition rsplit rstrip split splitlines startswith strip "
           "swapcase title translate upper zfill",
    "list": "__add__ __class_getitem__ __contains__ __delitem__ __getitem__ __iadd__ __imul__ __iter__ __len__ __mul__ __reversed__ "
            "__rmul__ __setitem__ append clear copy count extend index insert pop remove reverse sort",
    "tuple": "__add__ __class_getitem__ __contains__ __getitem__ __getnewargs__ __iter__ __len__ __mul__ __rmul__ count index",
    "dict": "__class_getitem__ __contains__ __delitem__ __getitem__ __ior__ __iter__ __len__ __or__ __reversed__ __ror__ __setitem__ "
            "clear copy fromkeys get items keys pop popitem setdefault update values",
}
# what builtins raise for a None argument (an optional value that is None); OPTARG: builtins that
# take None (or an optional value) themselves
NONEARG: dict[str, str] = {"len": "object of type 'NoneType' has no len()", "dict": "'NoneType' object is not iterable",
                           "int": "int() argument must be a string, a bytes-like object or a real number, not 'NoneType'",
                           "float": "float() argument must be a string or a real number, not 'NoneType'",
                           "ord": "ord() expected string of length 1, but NoneType found",
                           "os.system": "expected str, bytes or os.PathLike object, not NoneType",
                           "os.fspath": "expected str, bytes or os.PathLike object, not NoneType",
                           "abs": "bad operand type for abs(): 'NoneType'", "round": "type NoneType doesn't define __round__ method",
                           "chr": "'NoneType' object cannot be interpreted as an integer",
                           "os.path.exists": "stat: path should be string, bytes, os.PathLike or integer, not NoneType"}
OPTARG: list[str] = "str repr ascii bool input min max sys.exit exit quit".split()
# what those return (for None itself, which always raises)
NONERET: dict[str, str] = {"len": "int", "int": "int", "float": "float", "ord": "int", "os.system": "int", "os.path.exists": "bool"}
# builtins whose own code (not CALLS) takes a str, list, dict or tuple
OPTCALLS: list[str] = "sorted list dict min max sum any all".split()
# builtins that keep no reference to their arguments
NOREF: list[str] = "print str repr len bool sum sorted list tuple min max any all enumerate reversed zip isinstance hash".split()

# node kinds the parser accepts but code generation rejects, where it compiles them: an
# imported module may use them in functions the program never calls
UNSUPPORTED: dict[str, str] = {
    "nonlocal": "'nonlocal' is not supported",
    "subclass": "class inheritance is not supported", "lambda": "lambda is not supported",
    "yield": "'yield' is not supported (there are no generator functions)", "set": "set literals are not supported",
    "setcomp": "set literals are not supported", "dictcomp": "dict comprehensions are not supported",
    "nestedcomp": "nested comprehensions are not supported", "starred": "starred expressions (*x) are not supported",
    "dstar": "star arguments are not supported", "bytes": "bytes literals are not supported (there is no bytes type)",
    "ellipsis": "Ellipsis (...) is not supported", "complex": "complex numbers are not supported",
    "walrus": "assignment expressions (:=) are not supported", "await": "'await' is not supported",
    "async": "'async' statements are not supported",
    "asynccomp": "asynchronous comprehensions are not supported",
    "sliceitem": "a slice inside a tuple subscript (x[a:b, c]) is not supported", "match": "'match' statements are not supported",
    "typealias": "'type' statements are not supported",
}
# decorators that an imported module may apply to a def ("f") or a class ("c") Pystachy leaves
# uncompiled until the program uses it: applying them when the module's code runs calls no code
# of the program (over object.__new__, which makes an object of the class, only those marked "o")
INERT_DECOS: dict[str, str] = {"typing.overload": "f", "typing.final": "fco", "typing.no_type_check": "fco", "typing.override": "fco",
                               "staticmethod": "f", "classmethod": "f", "property": "f", "dataclasses.dataclass": "c",
                               "typing.runtime_checkable": "c", "object.__new__": "c"}
# node kinds that evaluate without effects
INERT: dict[str, bool] = {}
for _k in "int float str bytes complex None True False ellipsis noann omit".split():
    INERT[_k] = True
# builtins that call no code of the program and have no other effect, given values of builtin types
PURE: dict[str, bool] = {}
for _k in ("abs all any ascii bin bool bytes callable chr complex dict divmod enumerate filter float format frozenset hash hex "
           "int isinstance issubclass iter len list map max min object oct ord pow range repr reversed round set slice sorted "
           "str sum tuple zip __pys_repr __pys_str __pys_ascii typing.cast os.getcwd os.getenv os.environ.get").split():
    PURE[_k] = True
# encoding= names of UTF-8 (1) and Latin-1 (2) as CPython's codec lookup finds them (see codec()):
# a str holds the file's bytes either way, which is what CPython's str holds for a Latin-1 file
CODECS: dict[str, int] = {}
for _k in "utf8 u8 utf utf8_ucs2 utf8_ucs4 cp65001".split():
    CODECS[_k] = 1
for _k in "latin1 latin l1 iso8859_1 iso_8859_1 iso_8859_1_1987 iso_ir_100 iso8859 8859 cp819 ibm819 csisolatin1".split():
    CODECS[_k] = 2


def codec(e: str) -> int:
    # 1 UTF-8, 2 Latin-1, 0 another (runtime.c's codec()): the name normalized is an alias, or one
    # with "." read as "_", or the codec's module name
    n = normcodec(e)
    if n.find(".") >= 0:
        return CODECS.get(n.replace(".", "_"), 0)
    return 1 if n == "utf_8" else 2 if n == "latin_1" else CODECS.get(n, 0)


def normcodec(e: str) -> str:
    # an encoding's name normalized as CPython's codec lookup does: lowercase, and a run of
    # characters other than ASCII letters, digits and "." is one "_" between them
    n = ""
    punct = False
    for c in e:
        if c >= "A" and c <= "Z":
            n += "_" if punct and n != "" else ""
            n += c.lower()
            punct = False
        elif (c >= "a" and c <= "z") or (c >= "0" and c <= "9") or c == ".":
            n += "_" if punct and n != "" else ""
            n += c
            punct = False
        else:
            punct = True
    return n
# the most positional arguments a builtin takes: more are a compile error (a TypeError in CPython)
ARITY: dict[str, int] = {"len": 1, "repr": 1, "ascii": 1, "abs": 1, "ord": 1, "chr": 1, "bool": 1, "float": 1, "list": 1,
                         "dict": 1, "str": 1, "sorted": 1, "any": 1, "all": 1, "input": 1, "int": 2, "round": 2,
                         "divmod": 2, "sum": 2, "pow": 3}
# Builtin methods, "ret:arg,arg=default". *X: passed/returned as an 8-byte slot; #: element
# type descriptor; T: list element, K/V: dict key/value, S: the receiver's own type.
# Each maps to the C function pys_<type>_<method>.
METHODS: dict[str, str] = {
    "str.join": "str:list[str]", "str.split": "list[str]:str=null,int=-1", "str.strip": "str:str=null",
    "str.lstrip": "str:str=null", "str.rstrip": "str:str=null", "str.startswith": "bool:str,int=0,int=9223372036854775807",
    "str.endswith": "bool:str,int=0,int=9223372036854775807", "str.find": "int:str,int=0,int=9223372036854775807", "str.rfind": "int:str,int=0,int=9223372036854775807",
    "str.index": "int:str,int=0,int=9223372036854775807", "str.rindex": "int:str,int=0,int=9223372036854775807", "str.count": "int:str,int=0,int=9223372036854775807", "str.replace": "str:str,str", "str.upper": "str:", "str.lower": "str:",
    "str.isdigit": "bool:", "str.isalpha": "bool:", "str.isalnum": "bool:", "str.isspace": "bool:",
    "str.isupper": "bool:", "str.islower": "bool:", "str.ljust": "str:int,str=null", "str.rjust": "str:int,str=null",
    "str.center": "str:int,str=null", "str.zfill": "str:int", "str.rsplit": "list[str]:str=null,int=-1",
    "str.partition": "tuple[str,str,str]:str", "str.rpartition": "tuple[str,str,str]:str", "str.removeprefix": "str:str",
    "str.removesuffix": "str:str", "str.swapcase": "str:", "str.capitalize": "str:", "str.title": "str:", "str.casefold": "str:",
    "str.istitle": "bool:", "str.isascii": "bool:", "str.isdecimal": "bool:", "str.isnumeric": "bool:",
    "str.splitlines": "list[str]:bool=0", "str.expandtabs": "str:int=8",
    "list.append": "None:*T", "list.pop": "*T:int=-1", "list.insert": "None:int,*T", "list.extend": "None:S",
    "list.index": "int:*T,#,int=0,int=9223372036854775807", "list.count": "int:*T,#", "list.remove": "None:*T,#", "list.reverse": "None:",
    "list.copy": "S:", "list.clear": "None:",
    "dict.get": "*V:*K,*V=0", "dict.pop": "*V:*K", "dict.setdefault": "*V:*K,*V", "dict.keys": "list[K]:",
    "dict.values": "list[V]:", "dict.items": "list[tuple[K,V]]:", "dict.clear": "None:", "dict.copy": "S:",
    "file.read": "str:int=-1", "file.readline": "str:", "file.readlines": "list[str]:", "file.write": "int:str",
    "file.writelines": "None:list[str]", "file.close": "None:", "file.flush": "None:",
    "float.hex": "str:", "float.is_integer": "bool:",
}
# the IR's ops (Ins.op) and their effects (docs/typed-ir.md 3.4 and 3.7, and FX below): T ends
# a block; an rt op has its runtime function's effects (RUNTIME), a call or an init its callee's
# summary (IFn.fx); a raw op is LLVM text that loads, stores or computes (never a call), whose
# letters its text gives (rawfx)
IROPS: dict[str, str] = {
    "raw": "*", "slot": "", "rt": "*", "call": "*", "init": "*", "br": "T", "cbr": "T", "check": "T R",
    "ret": "T", "ret.none": "T", "raise": "T R N", "unreachable": "T", "phi": "", "select": "", "ovf": "",
    "list.load": "rL",
    "landing": "T", "throw": "T R N", "exc.match": "",
}
# the LLVM instructions a raw op may not be: the ones that end a block, and phi and call (ops of their own)
LLNOTRAW: dict[str, bool] = {}
for _k in "ret br switch indirectbr invoke callbr resume catchswitch catchret cleanupret unreachable phi call tail musttail notail".split():
    LLNOTRAW[_k] = True
# the optimizations, passes over each IFn once the program is built (docs/typed-ir.md 7.1), which
# PYSTACHY_OPT turns off: "-name", comma-separated, or "-all"
OPTS: list[str] = ["listget", "dictfuse"]
# what bounds dictfuse's work: the depth of the chain of values Gen.canon follows (the
# self-compile's deepest is 18), the ops Gen.reaching walks back over (85) and the lookups that
# hold at once (7)
CANON_DEPTH = 1000
REACH = 256
LOOKUPS = 32
# Effect letters: R may raise (in a program that has a try, the raise allocates its exception, so a
# collection may run before a handler takes it; if none does, the raise prints its message, flushes
# stdout and exits); N never returns; A allocates on the way to returning (a collection may run, and
# running out of memory ends the program); U may run user code, and so has every other letter (U?:
# when the static type, the descriptor of a # parameter, holds a class); I does I/O, or uses the
# process or global runtime state; rL wL, rD wD, rO wO, rG wG, rF wF read or write lists, dicts,
# objects' fields and flags, globals and their flags, files. Strings and tuples are immutable, slots
# are never address-taken, dict keys are ints, strs, or tuples of ints, bools, strs and None
# (key_problem), whose hash and == run no user code, and what an operation writes into an object it
# makes itself (list.copy, str.split, init's argument list) no other code has seen: they need no
# letter. N is a property of one op: an effect summary (IFn.fx) leaves it out. The end of the
# program (an error, an exit) flushes stdout and closes the open files: R and N stand for that. A
# collection closes the open files nothing refers to any more (and reports a failed close on
# stderr), which A stands for, not I, rF or wF: when a dropped file is closed is unspecified (README:
# at a collection or at exit, not at once as in CPython), so moving an A op may change it, as any
# change to the program's allocations does.
FX: list[str] = "R N A U I rL wL rD wD rO wO rG wG rF wF".split()
FXBIT: dict[str, int] = {}
for _j in range(len(FX)):
    FXBIT[FX[_j]] = 1 << _j
# the runtime functions the compiler declares: "result:params|effects|symbol", with types as the
# compiler spells them and S the receiver, T K V its element, key and value types, *X a value
# in an 8-byte slot (i64 in the LLVM binding), # the descriptor of the static type the operation
# works on (Ins.x), %X an LLVM type X that has no spelling (%ovf: {i64, i1}). "" as symbol means
# pys_<key, with . as _>. rt() checks each call against its entry, tools/check_runtime.py checks
# the entries against runtime.c (their LLVM types, and the effects its call graph shows)
RUNTIME: dict[str, str] = {
    # lists
    "list.new": "list[T]:int|A|", "list.get": "*T:S,int|R rL|", "list.set": "None:S,int,*T|R rL wL|",
    "list.append": "None:S,*T|A rL wL|", "list.pop": "*T:S,int|R rL wL|", "list.del": "None:S,int|R rL wL|",
    "list.insert": "None:S,int,*T|A rL wL|", "list.extend": "None:S,S|A rL wL|", "list.slice": "S:S,int,int|A rL|",
    "list.copy": "S:S|A rL|", "list.clear": "None:S|rL wL|", "list.add": "S:S,S|A rL|", "list.mul": "S:S,int|R A rL|",
    "list.imul": "None:S,int|R A rL wL|", "list.reverse": "None:S|rL wL|", "list.find": "int:S,*T,#|rL rD U?|",
    "list.index": "int:S,*T,#,int,int|R A I rL rD U?|", "list.index_as": "int:S,*T,#,int,int,bool,int,%ptr|R A I rL rD U?|", "list.count": "int:S,*T,#|rL rD U?|", "list.remove": "None:S,*T,#|R rL wL rD U?|",
    "list.sort_r": "None:S,#,bool|R A I rL wL rD U?|", "list.minmax": "*T:S,#,bool|R rL rD U?|",
    "any": "bool:list[T]|rL|", "all": "bool:list[T]|rL|", "sum.int": "int:list[T],int|R rL|",
    "sum.float": "float:list[float],float|rL|", "sum.float_int": "float:list[float],int|rL|", "sum.int_float": "float:list[T],float|rL|",
    "range.len": "int:int,int,int|R|", "range.has": "bool:int,int,int,int|R|", "range.list": "list[int]:int,int,int|R A|",
    # dicts: keys are ints, strs, or tuples of int, bool, str, None and such tuples (Dict.kind 0, 1,
    # or the tuple's descriptor, passed as an int), which hash, compare and print (a KeyError's
    # message) without user code; that repr is runtime.c's, which can reach pys_repr_enter: I
    "dict.new": "dict[K,V]:int,int|A|", "dict.has": "bool:S,*K|rD|", "dict.getitem": "*V:S,*K|R A I rD|",
    "dict.get": "*V:S,*K,*V|rD|", "dict.set": "None:S,*K,*V|A rD wD|", "dict.pop": "*V:S,*K|R A I rD wD|",
    "dict.pop_default": "*V:S,*K,*V|R A I rD wD|", "dict.setdefault": "*V:S,*K,*V|A rD wD|", "dict.clear": "None:S|wD|",
    "dict.getbox": "*V:S,*K,*V|A rD|", "dict.popbox": "*V:S,*K,*V|R A I rD wD|",
    "dict.copy": "S:S|A rD|", "dict.from": "S:S|A rD|", "dict.keys": "list[K]:S|A rD|", "dict.values": "list[V]:S|A rD|",
    "dict.items": "list[tuple[K,V]]:S|A rD|", "dict.end": "int:S|rD|", "dict.next": "int:S,int,int,int|R rD|",
    "dict.prev": "int:S,int,int,int|R rD|", "dict.key": "*K:S,int|rD|", "dict.val": "*V:S,int|rD|",
    "dict.find": "int:S,*K|rD|", "dict.entry": "int:S,*K|R A I rD|", "dict.entry_set": "None:S,int,*V|rD wD|",
    # strings
    "str.get": "str:S,int|R A|", "str.slice": "str:S,int,int|A|", "str.add": "str:S,str|A|", "str.mul": "str:S,int|R A|",
    "str.contains": "bool:S,str||", "str.join": "str:S,list[str]|R A rL|", "str.split": "list[str]:S,str,int|R A|",
    "str.rsplit": "list[str]:S,str,int|R A|", "str.splitlines": "list[str]:S,bool|A|", "str.strip": "str:S,str|A|",
    "str.lstrip": "str:S,str|A|", "str.rstrip": "str:S,str|A|", "str.startswith": "bool:S,str,int,int||",
    "str.endswith": "bool:S,str,int,int||", "str.find": "int:S,str,int,int||", "str.rfind": "int:S,str,int,int||",
    "str.count": "int:S,str,int,int||", "str.index": "int:S,str,int,int|R|", "str.rindex": "int:S,str,int,int|R|",
    "str.replace": "str:S,str,str|A|", "str.upper": "str:S|A|", "str.lower": "str:S|A|", "str.swapcase": "str:S|A|",
    "str.capitalize": "str:S|A|", "str.title": "str:S|A|", "str.casefold": "str:S|A|", "str.isdigit": "bool:S||",
    "str.isalpha": "bool:S||", "str.isalnum": "bool:S||", "str.isspace": "bool:S||", "str.isupper": "bool:S||",
    "str.islower": "bool:S||", "str.istitle": "bool:S||", "str.isascii": "bool:S||", "str.isdecimal": "bool:S||",
    "str.isnumeric": "bool:S||", "str.ljust": "str:S,int,str|R A|", "str.rjust": "str:S,int,str|R A|",
    "str.center": "str:S,int,str|R A|", "str.zfill": "str:S,int|R A|", "str.partition": "tuple[str,str,str]:S,str|R A|",
    "str.rpartition": "tuple[str,str,str]:S,str|R A|", "str.removeprefix": "str:S,str|A|", "str.removesuffix": "str:S,str|A|",
    "str.expandtabs": "str:S,int|A|", "str.int": "str:int|A|", "str.float": "str:float|A|", "str.list": "list[str]:str|R A|",
    "chr": "str:int|R A|", "ord": "int:str|R|", "ascii": "str:str|A|", "pct_char": "str:str|R|", "pct_chr": "str:int|R A|",
    # numbers
    "floordiv": "int:int,int|R|", "mod": "int:int,int|R|", "pow": "int:int,int|R|", "powmod": "int:int,int,int|R|",
    "shl": "int:int,int|R|", "shr": "int:int,int|R|", "idiv": "float:int,int|R|", "fdiv": "float:float,float|R|",
    "ffloordiv": "float:float,float|R|", "fmod": "float:float,float|R|", "fpow": "float:float,float|R|", "cmp_if": "int:int,float||",
    "f2i": "int:float|R|", "round": "int:float|R|", "round_n": "float:float,int|R|", "round_int": "int:int,int|R|", "floor": "int:float|R|",
    "ceil": "int:float|R|", "int.str": "int:str,int|R A|", "float.str": "float:str|R A|", "float.hex": "str:float|A|",
    "float.is_integer": "bool:float||", "fabs": "float:float||fabs",
    "ovf.sadd": "%ovf:int,int||llvm.sadd.with.overflow.i64", "ovf.ssub": "%ovf:int,int||llvm.ssub.with.overflow.i64",
    "ovf.smul": "%ovf:int,int||llvm.smul.with.overflow.i64",
    "m.sqrt": "float:float|R|", "m.sin": "float:float|R|", "m.cos": "float:float|R|", "m.tan": "float:float|R|",
    "m.asin": "float:float|R|", "m.acos": "float:float|R|", "m.atan": "float:float|R|", "m.sinh": "float:float|R|",
    "m.cosh": "float:float|R|", "m.tanh": "float:float|R|", "m.exp": "float:float|R|", "m.log": "float:float|R|",
    "m.log2": "float:float|R|", "m.log10": "float:float|R|", "m.fabs": "float:float|R|", "m.log1p": "float:float|R|",
    "m.expm1": "float:float|R|", "m.exp2": "float:float|R|", "m.cbrt": "float:float|R|", "m.degrees": "float:float||",
    "m.radians": "float:float||", "m.pow": "float:float,float|R|", "m.atan2": "float:float,float||",
    "m.hypot": "float:float,float||", "m.fmod": "float:float,float|R|", "m.copysign": "float:float,float||",
    "m.logb": "float:float,float|R|", "m.trunc": "int:float|R|", "m.gcd": "int:int,int|R|", "m.lcm": "int:int,int|R|",
    "m.isqrt": "int:int|R|", "m.factorial": "int:int|R|", "m.comb": "int:int,int|R|", "m.perm": "int:int,int|R|",
    "m.isfinite": "bool:float||", "m.isinf": "bool:float||", "m.isnan": "bool:float||", "m.asinh": "float:float|R|",
    "m.acosh": "float:float|R|", "m.atanh": "float:float|R|", "m.erf": "float:float|R|", "m.erfc": "float:float|R|",
    "m.ldexp": "float:float,int|R|", "m.frexp": "tuple[float,int]:float|A|", "m.modf": "tuple[float,float]:float|A|",
    "m.nextafter": "float:float,float||", "m.ulp": "float:float||", "m.remainder": "float:float,float|R|",
    "m.fma": "float:float,float,float|R|",
    # any type, by its descriptor
    "eq": "bool:*T,*T,#|rL rD U?|", "cmpop": "int:*T,*T,#,int|R rL rD U?|", "repr": "str:*T,#|A I rL rD U?|",
    "format": "str:*T,#,str|R A I rL rD U?|", "default_repr": "str:str,%ptr|A|", "repr_enter": "bool:%ptr|I|",
    "repr_leave": "None:%ptr|I|", "alloc": "%ptr:int|A|", "box": "%ptr:*T|A|", "unpack_check": "None:int,int|R|",
    # errors and the process
    "raise": "None:str,str|R N|", "exit": "None:int|R N I|", "exit_msg": "None:str|R N I|", "argv": "list[str]:|I|",
    "platform": "str:|A|", "errno": "int:str|R A|", "system": "int:str|R I|", "execv": "None:str,list[str]|R N A I rL|", "getpid": "int:|I|", "exists": "bool:str|I|",
    "path_join": "str:str,str|A|", "realpath": "str:str|R A I|", "getenv": "opt[str]:str,opt[str]|A I|", "remove": "None:str|R A I|", "rmdir": "None:str|R A I|",
    "mkdtemp": "str:|R A I|", "time": "float:|I|", "time_ns": "int:|I|", "monotonic": "float:|I|", "monotonic_ns": "int:|I|",
    "process_time": "float:|I|", "process_time_ns": "int:|I|", "sleep": "None:float|R I|", "sleep_int": "None:int|R I|",
    "setrecursionlimit": "None:int|R I|", "getrecursionlimit": "int:|I|",
    # exceptions (runtime.c's "exceptions"); a landing's pys_exc_begin runs the unwind actions: it
    # closes with-files (which may raise) and gives a list being sorted its items back. str() and
    # repr() of an exception object run its class's __str__ and __repr__ (through its ExcClass)
    "eh_on": "None:|I|", "try_mark": "int:|I|", "exc.handled": "exc:|I|", "exc.restore": "None:exc|I|",
    "exc.begin": "exc:exc,int|R I wL rF wF|", "exc.in": "int:exc,str||", "exc.str": "str:exc|U|", "exc.repr": "str:exc|A U|",
    "exc.new": "exc:str,str,str|A|", "exc.exit": "exc:int,str,str|A|", "exc.detail": "exc:exc,str||", "throw": "None:exc|R N|",
    "exc.user": "exc:%ptr|A|", "exc.obj": "%ptr:exc||", "exc.id": "%ptr:exc||", "exc.ostr": "str:%ptr|U|", "exc.orepr": "str:%ptr|U|",
    "exc.brepr": "str:%ptr,str|A|", "exc.cls": "str:%ptr|A|", "exc.name": "str:exc|A|", "exc.errcls": "str:int|A|",
    "reraise": "None:|R N|", "unwind_file": "None:file|I|", "unwind_pop": "None:|I|",
    "personality": "%i32:%i32,%i32,int,%ptr,%ptr|I|",
    "init": "None:%i32,%ptr,%ptr,%ptr,int|A I|", "finish": "None:|I rF wF|", "frameaddress": "%ptr:%i32||llvm.frameaddress.p0",
    # files and the standard streams
    "write": "None:str,int|R I rF wF|", "input": "str:str|R A I rF wF|", "open": "file:str,str,str,str,int|R A I rF|", "std": "file:int||",
    "file.read": "str:S,int|R A I rF wF|", "file.readline": "str:S|R A I rF wF|", "file.readlines": "list[str]:S|R A I rF wF|",
    "file.write": "int:S,str|R A I rF wF|", "file.writelines": "None:S,list[str]|R A I rL rF wF|",
    "file.flush": "None:S|R I rF wF|", "file.close": "None:S|R I rF wF|", "file.drop": "None:S|R I rF wF|",
    "file.closed": "bool:S|rF|", "file.name": "str:S|A rF|", "file.mode": "str:S|A rF|",
}
# LLVM symbol -> RUNTIME key (spelt out here as rtsym does: module code calls no function before
# the last def has run, which spares the compiled functions a check that each callee is defined)
RTSYM: dict[str, str] = {}
for _k in RUNTIME:
    _s = RUNTIME[_k][RUNTIME[_k].rfind("|") + 1 :]
    RTSYM[_s if _s != "" else "pys_" + _k.replace(".", "_")] = _k


def lt(t: str) -> str:
    if t == "int":
        return "i64"
    if t == "float":
        return "double"
    if t == "bool":
        return "i1"
    if t == "None":
        return "void"
    if t == "%slot":
        return "i64"  # (the IR's pseudo-type of a value in an 8-byte container slot)
    return "ptr"


def rtt(t: str) -> str:
    return "i64" if t == "bool" else lt(t)


def rtll(t: str) -> str:
    # the LLVM type of a type of a RUNTIME signature
    if t.startswith("*"):
        return "i64"
    if t == "S" or t == "#":
        return "ptr"
    if t == "%ovf":
        return "{i64, i1}"
    if t.startswith("%"):
        return t[1:]
    return rtt(t)


def rtsig(k: str) -> list[str]:
    # the result and parameter types of runtime function k, as RUNTIME spells them
    e = RUNTIME[k]
    c = e.find(":")
    ps = [e[:c]]
    for p in e[c + 1 : e.find("|")].split(","):
        if p != "":
            ps.append(p)
    return ps


def rtsym(k: str) -> str:
    s = RUNTIME[k][RUNTIME[k].rfind("|") + 1 :]
    return s if s != "" else "pys_" + k.replace(".", "_")


def runtime_decl(k: str) -> str:
    ps = rtsig(k)
    return f"declare {rtll(ps[0])} @{rtsym(k)}({', '.join([rtll(p) for p in ps[1:]])})"


# every effect letter but N (it is no summary's): U's, and a summary not computed yet
FXALL = (1 << len(FX)) - 1 - FXBIT["N"]
# what a raw op that loads or stores through an address other than a slot's, a global's or a
# field's may read or write: a list's or a dict's header or items (or a tuple's items, which need
# no letter); and an object's fields, for an address the IR does not show to be a field's
RAWR = FXBIT["rL"] | FXBIT["rD"] | FXBIT["rO"]
RAWW = FXBIT["wL"] | FXBIT["wD"] | FXBIT["wO"]


def fxmask(letters: str) -> int:
    # effect letters (FX) as bits (U: FXALL)
    m = 0
    for x in letters.split():
        if x == "U":
            return FXALL
        m |= FXBIT[x]
    return m


def fxs(m: int) -> str:
    # bits of effect letters as letters
    return " ".join([x for x in FX if m & FXBIT[x] != 0])


def optimizations() -> dict[str, bool]:
    # the optimizations to run (OPTS): every one but those PYSTACHY_OPT turns off ("-name",
    # comma-separated; "-all": every one), as name -> True
    on: dict[str, bool] = {}
    for o in OPTS:
        on[o] = True
    for w in os.getenv("PYSTACHY_OPT", "").split(","):
        w = w.strip()
        if w == "-all":
            on = {}
        elif w.startswith("-") and w[1:] in OPTS:
            if w[1:] in on:
                on.pop(w[1:])
        elif w != "":
            fail(f"PYSTACHY_OPT: no optimization {w} (it takes {', '.join(['-' + o for o in OPTS])} or -all, comma-separated)", 0)
    return on


def rawfx(s: str, fa: dict[str, bool]) -> int:
    # the effects (FX bits) of a raw op, whose LLVM text s loads, stores or computes: a load or a
    # store of a slot (%name.N, an alloca, which is never address-taken) has none, of a global
    # (@name) rG or wG, of an object's field or flag (an address in fa, IFn.fa) rO or wO; one
    # through another address may read (RAWR) or write (RAWW) a list or a dict
    st = s.startswith("store ")
    if not st and not s.startswith("load ", s.find(" = ") + 3):
        return 0
    a = s.rfind(" ") + 1  # where the address is: the last word of "load T, ptr A" and "store T V, ptr A"
    if s.startswith("@", a):
        return FXBIT["wG"] if st else FXBIT["rG"]
    if s.find(".", a) >= 0:
        return 0  # (a temporary, %tN, has no dot)
    if len(fa) > 0 and s[a:] in fa:
        return FXBIT["wO"] if st else FXBIT["rO"]
    return RAWW if st else RAWR


class RtFn:
    # a runtime function, as its RUNTIME entry k gives it
    def __init__(self, k: str):
        e = RUNTIME[k]
        fx = e[e.find("|") + 1 : e.rfind("|")]
        self.sym = rtsym(k)  # its LLVM symbol
        self.sig: list[str] = rtsig(k)  # its result and parameter types, as RUNTIME spells them
        self.ll: list[str] = [rtll(p) for p in self.sig]  # and as LLVM types
        self.decl = runtime_decl(k)  # its declare line
        self.fx = fxmask(fx.replace("U?", ""))  # its effects (FX bits), but U?
        self.q = "U?" in fx  # whether it has U? (U when the descriptor of its # parameter holds a class)


def tname(t: str) -> str:
    # the CPython name of a type, for error messages
    if t == "None":
        return "NoneType"
    if t == "file":
        return "TextIOWrapper"
    if t.startswith("opt["):
        return tname(t[4:-1]) + " | None"
    if t == "exc":
        return "BaseException"
    b = t.find("[")
    return t[:b] if b >= 0 else short(t)


def owner(name: str) -> str:
    # the module a qualified name belongs to (heapq$heappush: heapq), "" for the main program's
    o = name[: name.rfind("$")].replace("$", ".") if "$" in name else ""
    return "" if o == "__main__" else o


def short(name: str) -> str:
    # a function's or class's own name, without its module (heapq$heappush: heappush)
    return name[name.rfind("$") + 1 :]


def is_const(e: Node) -> bool:
    # literals: re-evaluating them on every call is indistinguishable from evaluating once
    k = e.kind
    if k == "int" or k == "float" or k == "str" or k == "True" or k == "False" or k == "None" or k == "noann":
        return True
    return k == "unary" and e.s == "-" and (e.kids[0].kind == "int" or e.kids[0].kind == "float")


def is_list(t: str) -> bool:
    return t.startswith("list[")


def is_dict(t: str) -> bool:
    return t.startswith("dict[")


def is_tuple(t: str) -> bool:
    return t.startswith("tuple[")


def is_opt(t: str) -> bool:
    # opt[T]: T | None for T str, int, float, bool, list, dict or tuple (a class type includes None already)
    return t.startswith("opt[")


def unopt(t: str) -> str:
    # the type an optional value has when it is not None
    return t[4:-1] if t.startswith("opt[") else t


def is_sopt(t: str) -> bool:
    # int, float or bool | None: a pointer to an immutable box of the value (runtime.c's pys_box)
    return t == "opt[int]" or t == "opt[float]" or t == "opt[bool]"


def meet(states: list[dict[str, bool]]) -> dict[str, bool]:
    # the names in every one of states (narrowed where paths join)
    r: dict[str, bool] = {}
    for nm in states[0]:
        ok = True
        for st in states[1:]:
            ok = ok and nm in st
        if ok:
            r[nm] = True
    return r


def nones(e: Node) -> bool:
    # is e a list display of None items, or a dict display of constant keys and None values
    for i in range(len(e.kids)):
        x = e.kids[i]
        if (e.kind == "list" or i % 2 == 1) and x.kind != "None":
            return False
        if e.kind == "dict" and i % 2 == 0 and x.kind != "str" and x.kind != "int":
            return False
    return True


def same_kind(a: str, b: str) -> bool:
    # are types a and b both lists or both dicts (a class may be named listing)
    return (is_list(a) and is_list(b)) or (is_dict(a) and is_dict(b))


def typestr(t: str) -> str:
    # type t for a message: an empty list or dict whose type is not known yet is "list" or "dict",
    # opt[T] is T | None, a builtin exception BaseException, a class its own name
    t = t.replace("[?,?]", "").replace("[?]", "")
    out: list[str] = []
    w = ""
    for c in t + ",":
        if c == "[" or c == "]" or c == ",":
            out.append("BaseException" if w == "exc" else short(w))
            out.append(c)
            w = ""
        else:
            w += c
    return optnames("".join(out)[:-1])


def optnames(t: str) -> str:
    # t (a type, or a message that names types) with each opt[T] written T | None
    while "opt[" in t:
        a = t.find("opt[")
        b = a + 4
        depth = 1
        while depth > 0 and b < len(t):
            depth += 1 if t[b] == "[" else -1 if t[b] == "]" else 0
            b += 1
        x = t[a + 4 : b - 1]
        t = t[:a] + (x if x == "None" else x + " | None") + t[b:]
    return t


def empty_display(e: Node) -> bool:
    return (e.kind == "list" or e.kind == "dict") and len(e.kids) == 0


def empty_default(n: Node, name: str, kind: str) -> bool:
    # is n name.setdefault(k, []) (kind "list") or name.setdefault(k, {}) (kind "dict")
    if n.kind != "call" or len(n.kids) != 3 or n.kids[0].kind != "attr" or n.kids[0].s != "setdefault":
        return False
    return n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == name and n.kids[2].kind == kind and len(n.kids[2].kids) == 0


def key_problem(t: str) -> str:
    # why t cannot be a dict's key type, or "": keys are ints, strs, or tuples whose items are ints,
    # bools, strs, str | None or such tuples (runtime.c hashes and compares them by descriptor)
    if t == "int" or t == "str" or (is_tuple(t) and key_items(t)):
        return ""
    if is_opt(t):
        return f"dict keys must be int or str, not {typestr(t)} (a key cannot be None)"
    return f"dict keys must be int or str, or tuples of int, bool, str and str | None items, not {typestr(t)}"


def lookable(a: str, b: str) -> bool:
    # can a value of type a be looked up among dict keys of type b, as CPython compares them: True
    # is 1, and None (a tuple's item) is no str
    if a == b or (a == "bool" and b == "int") or (b == "str" and (a == "None" or a == "opt[str]")):
        return True
    if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
        return False
    for i in range(len(targs(a))):
        if not lookable(targs(a)[i], targs(b)[i]):
            return False
    return True


def bool_for_int(a: str, b: str) -> bool:
    # does a key of type a hold a bool where the dict's keys, of type b, hold an int: the key it
    # finds is that int, but CPython's KeyError names the key as it is (KeyError: True, not 1),
    # and CPython keeps a key it adds as it is, a bool (Gen.bool_find, Gen.store_key)
    if a == "bool":
        return b == "int"
    if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
        return False
    for i in range(len(targs(a))):
        if bool_for_int(targs(a)[i], targs(b)[i]):
            return True
    return False


def none_items(t: str) -> str:
    # a tuple key type with str | None for its None items (a key's None says no more of the type)
    if t == "None":
        return "opt[str]"
    return f"tuple[{','.join([none_items(x) for x in targs(t)])}]" if is_tuple(t) else t


def key_items(t: str) -> bool:
    for x in targs(t):
        u = unopt(x)
        if x != "int" and x != "bool" and u != "str" and not (is_tuple(u) and key_items(u)):
            return False
    return True


def elem(t: str) -> str:
    return t[5:-1]


def targs(t: str) -> list[str]:
    out: list[str] = []
    depth = 0
    start = t.find("[") + 1
    if start == len(t) - 1:
        return out  # tuple[]: the empty tuple
    for i in range(start, len(t) - 1):
        c = t[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        elif c == "," and depth == 0:
            out.append(t[start:i])
            start = i + 1
    out.append(t[start:-1])
    return out


def subst(t: str, T: str, K: str, V: str, S: str) -> str:
    if t == "T":
        return T
    if t == "S":
        return S
    return t.replace("K", K).replace("V", V)


def llstr(s: str) -> str:
    out: list[str] = []
    for c in s:
        o = ord(c)
        if o < 32 or o > 126 or c == '"' or c == "\\":
            out.append("\\" + HEX[o >> 4] + HEX[o & 15])
        else:
            out.append(c)
    return "".join(out)


def hpush(h: list[int], x: int) -> None:
    # h is a binary min-heap (heapq's layout)
    h.append(x)
    i = len(h) - 1
    while i > 0 and h[(i - 1) // 2] > x:
        h[i] = h[(i - 1) // 2]
        i = (i - 1) // 2
    h[i] = x


def hpop(h: list[int]) -> int:
    top = h[0]
    x = h.pop()
    if len(h) > 0:
        i = 0
        while 2 * i + 1 < len(h):
            c = 2 * i + 1
            if c + 1 < len(h) and h[c + 1] < h[c]:
                c += 1
            if x <= h[c]:
                break
            h[i] = h[c]
            i = c
        h[i] = x
    return top


def hexn(v: int, n: int) -> str:
    s = ""
    for i in range(n):
        s = HEX[v & 15] + s
        v = v >> 4
    return s


def fbits(text: str) -> str:
    # exact IEEE-754 bits of a float literal, via float.hex(), as an LLVM hex constant
    h = float(text).hex()
    sign = 0
    if h.startswith("-"):
        sign = 2048
        h = h[1:]
    if h == "inf":
        return "0x" + hexn(sign + 2047, 3) + "0" * 13
    if h == "nan":
        return "0x7FF8000000000000"
    dot = h.find(".")
    p = h.find("p")
    frac = h[dot + 1 : p] if dot >= 0 else ""
    frac = frac + "0" * (13 - len(frac))
    e = 0 if h[2] == "0" else int(h[p + 1 :]) + 1023
    return "0x" + hexn(sign + e, 3) + frac.upper()


def names_in(t: Node, out: list[str]) -> None:
    # the names target t binds: a name, or those of a tuple, list or starred target
    if t.kind == "name":
        out.append(t.s)
    elif t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
        for k in t.kids:
            names_in(k, out)

def targets(st: Node, out: dict[str, bool]) -> None:
    # the names statement st assigns itself (not in its blocks)
    k = st.kind
    if k == "assign" or k == "annassign" or k == "augassign" or k == "for" or k == "with":
        names: list[str] = []
        if k == "with":
            for it in st.kids[:-1]:
                if len(it.kids) == 2:
                    names_in(it.kids[1], names)
        for i in range(len(st.kids) - 1 if k == "assign" else 0 if k == "with" else 1):
            names_in(st.kids[i], names)
        for nm in names:
            out[nm] = True


def collect(body: list[Node], out: dict[str, bool]) -> None:
    # Python's rule: a name assigned anywhere in a function is local to it (except ... as e too)
    for st in body:
        targets(st, out)
        for kid in st.kids:
            if kid.kind == "block":
                collect(kid.kids, out)
            elif kid.kind == "except":
                if kid.s != "":
                    out[kid.s] = True
                collect(kid.kids[1].kids, out)

def mark(names: list[str], sure: dict[str, bool], maybe: dict[str, bool], added: list[str]) -> None:
    # names are bound: added gets those that were not surely bound
    for nm in names:
        maybe[nm] = True
        if nm not in sure:
            sure[nm] = True
            added.append(nm)


def calls(n: Node, m: Mod) -> bool:
    # may statement n call a function of module m when it runs: it names one, or a class (a
    # decorator too), apart from the bodies of the functions it defines
    k = m.kinds.get(n.s.split(".")[0], "") if n.kind == "name" or n.kind == "deco" else ""
    if k == "f" or k == "c" or k.startswith("a:" + m.q):
        return True
    for x in n.kids:
        if not (n.kind == "def" and x.kind == "block") and calls(x, m):
            return True
    return False


def top_bindings(body: list[Node]) -> dict[str, int]:
    # how many module-level statements bind each name
    count: dict[str, int] = {}
    for st in body:
        names: dict[str, bool] = {}
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            names[st.s] = True
        elif st.kind != "import":
            collect([st], names)
        for a in st.kids if st.kind == "import" else []:
            names[a.s] = True
        for nm in names:
            count[nm] = count.get(nm, 0) + 1
    return count


def has_try(body: list[Node]) -> bool:
    # does body hold a try statement, also in the functions and classes it defines (a class with
    # bases is a subclass node whose first kid is the class)
    for st in body:
        if st.kind == "try":
            return True
        for kid in st.kids if st.kind != "subclass" else st.kids[0].kids:
            if kid.kind == "block" and has_try(kid.kids):
                return True
    return False


def name_nodes(n: Node, out: dict[str, bool]) -> None:
    # the names of every name node in n
    if n.kind == "name":
        out[n.s] = True
    for k in n.kids:
        name_nodes(k, out)


def calls_init(n: Node) -> bool:
    # does n hold a call of an __init__ method (outside the functions and classes it defines)
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].s == "__init__":
        return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    for k in n.kids:
        if calls_init(k):
            return True
    return False


def has_kind(n: Node, kind: str) -> bool:
    # does n hold a node of kind (outside the functions, classes and lambdas it defines)
    if n.kind == kind:
        return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    for k in n.kids:
        if has_kind(k, kind):
            return True
    return False


def reads(n: Node, name: str) -> bool:
    # does code n read name in its own scope where it may run: not after a return, raise, break or
    # continue of its block, as a list comprehension's own variable, in an annotation, which a
    # function does not evaluate, or in the functions and classes it defines
    k = n.kind
    if k == "name":
        return n.s == name
    if k == "def" or k == "class" or k == "subclass" or k == "lambda":
        return False
    if k == "listcomp":
        names: list[str] = []
        names_in(n.kids[1], names)
        if name in names:
            return reads(n.kids[2], name)
    for i in range(len(n.kids)):
        if not (k == "annassign" and i == 1) and reads(n.kids[i], name):
            return True
        x = n.kids[i].kind
        if k == "block" and (x == "return" or x == "raise" or x == "break" or x == "continue"):
            return False
    return False


def local_types(body: list[Node], out: dict[str, Node]) -> None:
    # a type for the names a function's body binds (not in the functions and classes it defines):
    # the annotation of one, or the type of a constant one is assigned
    for st in body:
        v = st.kids[-1] if st.kind == "assign" else st
        if v.kind == "unary" and v.s == "-":
            v = mk("int", "", v.line, []) if v.kids[0].kind == "True" or v.kids[0].kind == "False" else v.kids[0]  # (-True is -1)
        t = v.kind if v.kind == "int" or v.kind == "float" or v.kind == "str" else "bool" if v.kind == "True" or v.kind == "False" else ""
        for x in st.kids[:-1] if st.kind == "assign" and t != "" else st.kids[:0]:
            if x.kind == "name" and x.s not in out:
                out[x.s] = mk("name", t, st.line, [])
        if st.kind == "annassign" and st.kids[0].kind == "name" and st.kids[0].s not in out:
            out[st.kids[0].s] = st.kids[1]
        for kid in st.kids if st.kind != "def" and st.kind != "class" and st.kind != "subclass" else st.kids[:0]:
            if kid.kind == "block":
                local_types(kid.kids, out)
            elif kid.kind == "except":
                local_types(kid.kids[1].kids, out)


def refers(n: Node, name: str) -> bool:
    # does n read name (outside the functions and classes it defines)
    if n.kind == "name" and n.s == name:
        return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    for k in n.kids:
        if refers(k, name):
            return True
    return False


def all_imports(body: list[Node], out: list[str]) -> None:
    # the user modules that body imports, in its functions too
    for st in body:
        if st.kind == "uimport":
            for x in st.kids:
                out.append(x.s)
        for kid in st.kids:
            if kid.kind == "block":
                all_imports(kid.kids, out)
            elif kid.kind == "except":
                all_imports(kid.kids[1].kids, out)


def top_imports(body: list[Node]) -> list[str]:
    # the user modules that module-level code (body, not its functions) imports
    out: list[str] = []
    for st in body:
        if st.kind == "uimport":
            for x in st.kids:
                out.append(x.s)
        elif st.kind != "def" and st.kind != "class":
            for kid in st.kids:
                if kid.kind == "block":
                    out.extend(top_imports(kid.kids))
                elif kid.kind == "except":
                    out.extend(top_imports(kid.kids[1].kids))
    return out


def deleted(body: list[Node], out: dict[str, bool], defs: bool = False) -> None:
    # the names that del statements in body unbind (not in functions), and the end of an except
    # clause that binds a name (except E as e: e is unbound after it); with defs, also those its
    # def and class statements bind
    for st in body:
        if defs and (st.kind == "def" or st.kind == "class" or st.kind == "subclass"):
            out[st.s] = True
        if st.kind == "del":
            names: list[str] = []
            for t in st.kids:
                if t.kind == "name" or t.kind == "tuple" or t.kind == "list":
                    names_in(t, names)
            for nm in names:
                out[nm] = True
        if st.kind != "def" and st.kind != "class":
            for kid in st.kids:
                if kid.kind == "block":
                    deleted(kid.kids, out, defs)
                elif kid.kind == "except":
                    if kid.s != "":
                        out[kid.s] = True
                    deleted(kid.kids[1].kids, out, defs)


def none_assigns(body: list[Node], out: dict[str, list[Node]]) -> None:
    # every value module-level code (body, not its functions) assigns to each name; a name bound
    # any other way (for, with, +=, an annotation, unpacking) gets an "omit" node
    for st in body:
        k = st.kind
        if k == "assign":
            for t in st.kids[:-1]:
                names: list[str] = []
                names_in(t, names)
                for nm in names:
                    if nm not in out:
                        out[nm] = []
                    out[nm].append(st.kids[-1] if t.kind == "name" else mk("omit", "", st.line, []))
        elif k == "annassign" or k == "augassign" or k == "for" or k == "with":
            asg: dict[str, bool] = {}
            collect([st], asg)
            for nm in asg:
                if nm not in out:
                    out[nm] = []
                out[nm].append(mk("omit", "", st.line, []))
        for kid in st.kids:
            if kid.kind == "block" and st.kind != "def" and st.kind != "class":
                none_assigns(kid.kids, out)
            elif kid.kind == "except":
                if kid.s != "":
                    if kid.s not in out:
                        out[kid.s] = []
                    out[kid.s].append(mk("omit", "", kid.line, []))
                none_assigns(kid.kids[1].kids, out)


def local_names(body: list[Node], out: dict[str, bool]) -> None:
    # a function's locals: the names it assigns, deletes or defines (a def or class, which is an
    # error where it is compiled, as bound_in()'s are), but not a qualified name (M$x), which an
    # assignment to a module's attribute (M.x = ...) or a global M declares makes
    asg: dict[str, bool] = {}
    collect(body, asg)
    deleted(body, asg, True)
    for st in body:
        bound_in(st, asg)
    for nm in asg:
        if "$" not in nm:
            out[nm] = True


def import_reads(n: Node, sure: dict[str, bool], out: dict[str, bool], user: dict[str, bool]) -> None:
    # the names that code n of a function reads where no import in it has surely bound them yet
    # (sure: those an import before n has bound, to which n adds those it surely binds: in both
    # branches of an if, in a with block, not in a loop), and those its imports of Python modules
    # bind (user)
    if n.kind == "name" and n.s not in sure:
        out[n.s] = True
    for a in n.kids if n.kind == "import" else n.kids[:0]:
        sure[a.s] = True
        if n.s.startswith("from.") or not (builtin_module(a.kids[1].s) or a.kids[1].s == "typing_extensions"):
            user[a.s] = True
    if n.kind == "if":
        import_reads(n.kids[0], sure, out, user)
        then = dict(sure)
        import_reads(n.kids[1], then, out, user)
        import_reads(n.kids[2], sure, out, user)
        gone: list[str] = []
        for nm in sure:
            if nm not in then:
                gone.append(nm)
        for nm in gone:
            del sure[nm]
        if n.kids[0].kind == "True":
            for nm in then:
                sure[nm] = True
        return
    for k in n.kids if n.kind != "def" and n.kind != "class" and n.kind != "subclass" and n.kind != "lambda" else n.kids[:0]:
        import_reads(k, dict(sure) if k.kind == "block" and n.kind != "with" else sure, out, user)
    first = n.kids[0].kids[0] if n.kind == "try" and len(n.kids[0].kids) > 0 else n
    for a in first.kids if first.kind == "import" and first.s == "" else first.kids[:0]:
        # try: import m as x / ...: after the statement, x is bound unless the import raised,
        # which a read of it checks as it runs (Loader.fragile, Gen.modchk)
        sure[a.s] = True


def globals_in(body: list[Node], out: dict[str, bool]) -> None:
    for st in body:
        if st.kind == "global":
            for nm in st.kids:
                out[nm.s] = True
        for kid in st.kids:
            if kid.kind == "block":
                globals_in(kid.kids, out)
            elif kid.kind == "except":
                globals_in(kid.kids[1].kids, out)


def stmt_binds(st: Node, name: str) -> bool:
    # does statement st itself (not the blocks it holds) bind variable name
    k = st.kind
    names: list[str] = []
    if k == "assign":
        for t in st.kids[:-1]:
            names_in(t, names)
    elif k == "annassign" or k == "augassign" or k == "for":
        names_in(st.kids[0], names)
    elif k == "with":
        for it in st.kids[:-1]:
            if len(it.kids) == 2:
                names_in(it.kids[1], names)
    return name in names


def only_none(body: list[Node], name: str) -> bool:
    # do the statements in body (into blocks, not into defs and classes) bind variable name only
    # to None, by name = None
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        if stmt_binds(st, name) and not (st.kind == "assign" and nonexpr(st.kids[-1]) and assigns(st, name)):
            return False  # (also a, name = None, None)
        for kid in st.kids:
            if kid.kind == "block" and not only_none(kid.kids, name):
                return False
            if kid.kind == "except" and not only_none(kid.kids[1].kids, name):
                return False
    return True


def nonexpr(e: Node) -> bool:
    # is e None, or a conditional expression of None in both arms
    return e.kind == "None" or (e.kind == "ifexp" and nonexpr(e.kids[1]) and nonexpr(e.kids[2]))


def binds_other(body: list[Node], name: str) -> bool:
    # does code body bind name other than as an except clause's name (not in the functions and
    # classes it defines)
    for st in body:
        if stmt_binds(st, name) or ((st.kind == "def" or st.kind == "class" or st.kind == "subclass") and st.s == name):
            return True
        for a in st.kids if st.kind == "import" else st.kids[:0]:
            if a.s == name:
                return True
        for k in st.kids if st.kind != "def" and st.kind != "class" and st.kind != "subclass" else st.kids[:0]:
            if (k.kind == "block" and binds_other(k.kids, name)) or (k.kind == "except" and binds_other(k.kids[1].kids, name)):
                return True
    return False


def has_finally(body: list[Node]) -> bool:
    # does code body hold a try statement with a finally block (not in the functions and classes it defines)
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        for k in st.kids:
            if (k.kind == "block" and ((st.kind == "try" and k.s != "else" and k is not st.kids[0]) or has_finally(k.kids))) or (k.kind == "except" and has_finally(k.kids[1].kids)):
                return True
    return False


def binds_as(body: list[Node], name: str) -> bool:
    # does an except clause in code body bind name (not in the functions and classes it defines)
    for st in body:
        for k in st.kids if st.kind != "def" and st.kind != "class" and st.kind != "subclass" else st.kids[:0]:
            if (k.kind == "block" and binds_as(k.kids, name)) or (k.kind == "except" and (k.s == name or binds_as(k.kids[1].kids, name))):
                return True
    return False


def assigns(st: Node, name: str) -> bool:
    # is name a target of assignment st itself (not inside a tuple)
    for t in st.kids[:-1]:
        if t.kind == "name" and t.s == name:
            return True
    return False


def typed_default(body: list[Node], d: Node, ret: bool) -> bool:
    # is d the default value of a get() or setdefault() call that a statement in body (into blocks)
    # returns (ret: the function returns a list or dict) or assigns to an annotated variable, so
    # that the type expected there types it (see fill)
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        v = st.kids[-1] if len(st.kids) > 0 else st
        if ((st.kind == "return" and ret) or (st.kind == "annassign" and len(st.kids) == 3)) and v.kind == "call" and len(v.kids) == 3 and v.kids[2] is d:
            return v.kids[0].kind == "attr" and (v.kids[0].s == "get" or v.kids[0].s == "setdefault")
        for kid in st.kids:
            if kid.kind == "block" and typed_default(kid.kids, d, ret):
                return True
            if kid.kind == "except" and typed_default(kid.kids[1].kids, d, ret):
                return True
    return False


def aliases(n: Node, name: str) -> bool:
    # does n (outside its return statements: the callers are told, see guessed) give the container
    # that variable name holds to another variable, container, field or function, which could fill
    # it: x = name, [name], f(name), a or name; not print(name), len(name), sorted(name), for x in name
    if n.kind == "return" or n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    for i in range(len(n.kids)):
        kid = n.kids[i]
        if kid.kind == "name" and kid.s == name:
            if (n.kind == "assign" or n.kind == "annassign") and i == len(n.kids) - 1 and i > 0:
                return True
            if n.kind == "call" and i > 0 and not (n.kids[0].kind == "name" and n.kids[0].s in NOREF):
                return True
            if n.kind in "kw list tuple dict boolop".split() or (n.kind == "ifexp" and i > 0):
                return True
        elif aliases(kid, name):
            return True
    return False


def shows_items(n: Node, name: str) -> bool:
    # does n (outside the functions and classes it defines) assign variable name, or fill the
    # container it holds: name[k] = v, name += xs, name.append(v), insert, extend, setdefault, get
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    if stmt_binds(n, name):
        return True
    if n.kind == "assign":
        for t in n.kids[:-1]:
            if t.kind == "index" and t.kids[0].kind == "name" and t.kids[0].s == name:
                return True
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == name:
        if n.kids[0].s in "append insert extend setdefault get".split():
            return True
    for k in n.kids:
        if shows_items(k, name):
            return True
    return False


class Val:
    def __init__(self, v: str, t: str):
        self.v = v
        self.t = t


class FnInfo:
    def __init__(self, name: str, ll: str, node: Node, cls: str):
        self.name = name
        self.ll = ll
        self.node = node
        self.cls = cls
        self.params: list[str] = []
        self.ptypes: list[str] = []
        self.defaults: list[Node] = []
        self.dglob: list[str] = []  # global holding a default evaluated at def time, or ""
        self.uflags: dict[str, bool] = {}  # locals some read may find unassigned
        self.ret = "None"  # "" while a template's function is being compiled, before its first return
        self.mod = ""  # the dotted name of its module ("" for the main program)
        self.npos = -1  # how many parameters may be passed by position (-1: all; the rest are keyword-only)
        self.posonly = 0  # how many may only be passed by position
        # templates: a module-level function with an unannotated parameter, compiled per call for
        # the argument types (ptypes "" where unannotated) into the functions in insts
        self.generic = False
        self.insts: dict[str, FnInfo] = {}
        self.dtypes: list[str] = []  # the type of each default value evaluated at def time
        self.bad = ""  # why a template cannot be compiled (it is an error only if a call needs it)
        self.infer = False  # a template's function: its first return statement decides its return type
        self.noret = False  # a template's function that has no return and cannot end (it raises, or loops)
        self.inst = False  # a template's function, compiled for one list of argument types
        self.vararg = -1  # the index of a template's *args parameter (a tuple of the extra arguments), or -1
        self.varelem = ""  # its annotation (the type of each extra argument), or ""
        self.iters = False  # an __iter__ that returns an Iterator[T]: ret is the list[T] it steps through (see iter_ret)
        self.deco = ""  # a method's @staticmethod or @classmethod (whose cls names the class), or "": it takes self
        self.clsuse = False  # a class method that uses cls, which names the class that defines it (see cls_bound)
        self.orig = node  # and then its def statement as it was, before cls was renamed (see inherit)
        # a template's function: the parameters whose arguments are objects known not to be None
        # (a new object, self), which its isinstance(), hasattr() and "is None" tests read as such
        self.nnp: dict[str, bool] = {}


def takes_self(f: FnInfo) -> bool:
    # is f a method that takes its object as its first parameter (not a static or class method)
    return f.cls != "" and f.deco == ""


def clone(n: Node) -> Node:
    # a copy of tree n (a class method's def, compiled again for a class that inherits it)
    c = Node(n.kind, n.s, n.line)
    c.kids = [clone(k) for k in n.kids]
    c.chk = n.chk
    c.mchk = n.mchk
    c.depth = n.depth
    return c


def rename(n: Node, name: str, to: str) -> None:
    # the reads of name in n read to instead (a class method's cls is its class)
    if n.kind == "name" and n.s == name:
        n.s = to
    for k in n.kids:
        rename(k, name, to)


# ---------------------------------------------------------------- the IR
# Gen builds one IFn per compiled function: blocks of instructions (Ins), each an op string
# whose fields mean what the op says (docs/typed-ir.md 3.4). Until all of Gen builds ops, most
# are "raw": one line of LLVM text. Once the whole program is built, lowering prints the LLVM
# text of each IFn (lower).
# The lists an op starts with: shared, and never changed (Gen.program checks it). An op that has
# numbers, operands or labels gets lists of its own (most ops are raw and have none of them).
NONUMS: list[int] = []
NOVALS: list[Val] = []
NOLABELS: list[str] = []


class Ins:
    # one instruction: op decides which fields mean something
    def __init__(self, op: str, t: str, s: str):
        self.op = op  # a key of IROPS
        self.t = t  # its result type ("" if it defines no value; an rt op's as RUNTIME spells it), a slot's type
        # text immediate: for "raw", one line of LLVM text; a slot's name; an rt op's RUNTIME key; the
        # symbol a call calls; the module an init runs; a check's message "Kind: text"; the
        # exception a raise raises; ovf's operator + - *
        self.s = s
        # int immediate: a slot's kind (1: an "is assigned" flag), a hole (Gen.holes, from 1), the
        # number of the value a raw op defines (%tN; 0: none)
        self.k = 0
        # an rt op's descriptor of the static type it works on (for its # parameter): RUNTIME's U?
        # is U when it holds a class (O<id>), or an exception (E) in a program that makes objects of
        # exception classes
        self.x = ""
        self.r: list[int] = NONUMS  # the numbers of the values it defines, given when it was built
        self.a: list[Val] = NOVALS  # operands, in evaluation order (an rt op's typed as RUNTIME spells its parameters)
        self.b: list[str] = NOLABELS  # labels: the successors of br, cbr and check; a phi's predecessors


class Blk:
    # one basic block, which becomes one LLVM block
    def __init__(self, label: str):
        self.label = label  # "entry", "L<n>", or "" for one LLVM starts after a terminator
        self.code: list[Ins] = []
        # where an exception raised here goes: the landing block of the innermost try statement
        # of its function around it, or "" (it leaves the function)
        self.handler = ""


class Loop:
    # the shape of one loop, for loop passes and structured backends; lowering ignores it
    def __init__(self, kind: str, head: str, body: str, step: str, brk: str):
        self.kind = kind  # "while" "range" "rrange" "seq"
        self.mode = ""  # seq: "" enumerate zip reversed items keys values
        self.head = head  # the block that tests whether to go on
        self.body = body  # the block where its body starts
        self.step = step  # continue's target
        self.exit = brk  # break's target, after the else block
        self.seqs: list[Val] = []  # what a seq loop steps through
        # a seq loop's test of each of seqs leads to a block (tests) where the item it takes is the
        # one at idx (a list's or a str's index: 0 <= idx < its length when it was tested)
        self.tests: list[str] = []
        self.idx: list[str] = []
        self.ctr = ""  # the slot of its counter or index
        self.stop = Val("", "")  # a range loop's stop, evaluated once


class Try:
    # the shape of one try statement, for structured backends; lowering needs only Blk.handler
    def __init__(self, body: str):
        self.body = body  # the block where its body starts
        self.landing = ""  # the landing block of its except clauses ("" without them)
        self.final = ""  # the landing block of its finally block ("" without one)
        self.orelse = ""  # the block where its else block starts ("" without one)
        self.exit = ""  # where the normal path goes on: the copy of its finally block starts there


class IFn:
    # one compiled function: a function, a method, a module's code, a helper or a template's function
    def __init__(self, f: FnInfo):
        self.f = f  # f.ret is final once the IFn is complete
        self.ps: list[int] = []  # the indices of its parameters that are passed (a None-typed one is not)
        self.slots: list[Ins] = []  # entry-block storage ("slot" ops)
        self.blocks: list[Blk] = [Blk("entry")]
        self.loops: list[Loop] = []
        # message "Kind: text" -> the label of the block that raises it: one per function and
        # message, numbered at the first check of it, and placed after the function's code
        self.cold: dict[str, str] = {}
        # inside a try statement, a message's key is "<landing> <message>", and its cold block raises
        # the message to that landing block: the key -> the landing block
        self.coldh: dict[str, str] = {}
        self.tries: list[Try] = []
        self.pads = False  # whether it keeps landing pads (once the exception passes have run)
        # its effect summary (FX bits): every letter (but N) until Gen.effects computes it, once
        # the whole program is built
        self.fx: int = FXALL
        # the last number its builder gave (%tN, LN, %name.N), once it is complete: a pass that
        # adds values or blocks numbers them after it (the IR check checks that none is above it)
        self.n = 0
        self.fa: dict[str, bool] = {}  # the values that are addresses of an object's field or flag (Gen.fgep)


class Lookup:
    # a dict.has or dict.getitem (op, at position x of block blk of its IFn) of key k in dict d,
    # given as their canonical values (Gen.canon): a getitem or a set of the same d and k after
    # it may reuse the entry it finds (Gen.dictfuse)
    def __init__(self, op: Ins, blk: int, x: int, d: str, k: str):
        self.op = op
        self.blk = blk
        self.x = x  # its position in the block
        self.d = d
        self.k = k
        self.e = 0  # the number of the entry's index (%tN), once an op reuses it


class Values:
    # which values of an IFn are equal (Gen.canon), for dictfuse: each value's canonical value
    def __init__(self, fn: IFn, pl: dict[str, list[int]]):
        self.fn = fn
        self.pl = pl  # the blocks that branch to each block (Gen.preds)
        # by the number of the value a raw op or an rt op defines: its block * stride + its position
        # there (-1 for the other numbers), stride being more than the ops of any block (a block of
        # 50 xors a line for 24,000 lines holds more than 2^20)
        self.at: list[int] = [-1] * (fn.n + 1)
        self.stride = 1
        for b in fn.blocks:
            if len(b.code) >= self.stride:
                self.stride = len(b.code) + 1
        self.cn: dict[str, str] = {}  # value -> its canonical value, once asked
        self.same: dict[str, str] = {}  # a computation's text, with canonical operands -> the first value of it
        self.text: dict[str, str] = {}  # and that value -> the text
        self.depth = 0  # how many calls of Gen.canon are under way (at most CANON_DEPTH)
        for j in range(len(fn.blocks)):
            code = fn.blocks[j].code
            for x in range(len(code)):
                i = code[x]
                if i.op == "raw" and i.k > 0:
                    self.at[i.k] = j * self.stride + x
                elif i.op == "rt" and len(i.r) == 1:
                    self.at[i.r[0]] = j * self.stride + x


class Exit:
    # what leaving a block through break, continue or return first does (Gen.exits)
    def __init__(self, kind: str, v: str, handler: str):
        # "with": close the file v; "handler": restore v as the exception being handled (and unbind
        # name); "finally": run body, as where its try statement is: in nloops loops and nexcs
        # except clauses. It runs under handler, the landing block around the construct
        self.kind = kind
        self.v = v
        self.handler = handler
        self.name = ""
        self.body: list[Node] = []
        self.nloops = 0
        self.nexcs = 0
        self.entry = ""  # a finally block compiled once (Gen.try_): where it starts, ""  if each way out has a copy
        self.sel = ""  # the slot of the way out it goes on to, an index into conts
        self.conts: list[str] = []


class Frame:
    # the code generator's state for one function, saved while it compiles another
    def __init__(self, curfn: FnInfo, fn: IFn, blk: Blk):
        self.fn = fn
        self.blk = blk
        self.ltype: dict[str, str] = {}
        self.lreg: dict[str, str] = {}
        self.gdecl: dict[str, bool] = {}
        self.assigned: dict[str, bool] = {}
        self.compvars: dict[str, int] = {}
        self.loops: list[Loop] = []
        self.exits: list[Exit] = []
        self.wdepth: list[int] = []
        self.handler = ""
        self.excs: list[Val] = []
        self.shadows: list[list[str]] = []
        self.lcs: list[str] = []
        self.lct: list[str] = []
        self.ret = ""
        self.retann = False
        self.nn: dict[str, bool] = {}
        self.selfname = ""
        self.uflags: dict[str, bool] = {}
        self.lflag: dict[str, str] = {}
        self.nonevars: dict[str, int] = {}
        self.narrowed: dict[str, bool] = {}
        self.lkk: dict[str, str] = {}
        self.branch = 0
        self.modlevel = False
        self.lenient = False
        self.n = 0
        self.cur = ""
        self.term = False
        self.line = 0
        self.curfn = curfn


class ClassInfo:
    def __init__(self, name: str, node: Node):
        self.name = name
        self.node = node
        self.fields: list[str] = []
        self.fpos: dict[str, int] = {}  # field -> its index in fields (and in the struct)
        self.ftypes: dict[str, str] = {}
        self.fdefault: dict[str, Node] = {}
        self.fglob: dict[str, str] = {}
        self.fflag: dict[str, int] = {}  # field -> index of its "is assigned" flag in the struct
        self.methods: dict[str, FnInfo] = {}
        self.mod = ""
        self.bad = ""  # why a class of an imported module cannot be compiled: an error where it is used
        self.kwonly = False  # @dataclass(kw_only=True): its __init__ takes the fields by keyword only
        # an exception class: its base (a class of the program or a builtin exception class), and
        # the builtin exception class it derives from through it ("" for any other class)
        self.base = ""
        self.exc = ""
        self.nflag = 0  # the "is assigned" flags at the end of its struct (its own fields')
        self.leak = False  # its __init__ lets self escape before it ends
        self.flowed = False  # fl_fields has decided its flags


class Flow:
    # definite assignment over one scope: which reads may find their variable unassigned
    def __init__(self, tracked: dict[str, bool], defd: dict[str, bool]):
        self.tracked = tracked
        self.defd = defd  # names assigned on every path to here; " dead" marks unreachable code
        # every change to defd since the start, so that a branch is undone in the time it took
        # (not by copying defd): the key, and whether it was in defd before
        self.log: list[str] = []
        self.was: list[bool] = []
        # the innermost loop, if it is a while True (left only through break): what the states at
        # its breaks so far have in common (see fold)
        self.btrue = False
        self.bjoin: dict[str, bool] = {}  # the keys whose common state is not their state where the loop began: that state
        self.bany = False  # a break was folded
        self.bwas: dict[str, bool] = {}  # the keys changed in the loop: whether each was in defd where it began
        self.bnew: dict[str, bool] = {}  # the keys changed since the last break (or since the loop began)
        # the names the except clauses inside the innermost loop bind, and those the finally blocks
        # around them there may delete: a break unbinds them
        self.unb: list[str] = []
        self.marks: dict[str, bool] = {}
        self.call: dict[str, bool] = {}
        self.called = False
        # field mode, over __init__: which fields may be seen unassigned (".f" in defd = assigned)
        self.me = ""
        self.fields: list[str] = []
        self.unsafe: dict[str, bool] = {}
        # in an exception class's __init__: the fields super().__init__() surely assigns, whether it
        # lets self escape, and whether this __init__ does
        self.sup: list[str] = []
        self.base = ""  # (the class's base, whose __init__ it may call as Base.__init__(self, ...))
        self.leak = False
        self.escaped = False

    def exposed(self) -> None:
        # self escapes or __init__ returns: fields not assigned yet may be read unassigned
        if " dead" not in self.defd:
            for f in self.fields:
                if "." + f not in self.defd:
                    self.unsafe[f] = True

    def put(self, k: str) -> None:
        if k not in self.defd:
            if self.btrue:
                self.touch(k, False)
            self.defd[k] = True
            self.log.append(k)
            self.was.append(False)

    def drop(self, k: str) -> None:
        if k in self.defd:
            if self.btrue:
                self.touch(k, True)
            del self.defd[k]
            self.log.append(k)
            self.was.append(True)

    def touch(self, k: str, was: bool) -> None:
        # k changes in a while True loop: the next break looks at it (see fold)
        if k not in self.bwas:
            self.bwas[k] = was
        self.bnew[k] = True

    def undo(self, mark: int) -> None:
        # back to the state when the log had mark entries
        while len(self.log) > mark:
            k = self.log.pop()
            if self.btrue:
                self.bnew[k] = True
            if self.was.pop():
                self.defd[k] = True
            else:
                del self.defd[k]

    def since(self, mark: int) -> dict[str, bool]:
        # the state now, as the keys changed since the log had mark entries, each with whether
        # it is in defd (the other keys are as they were then), and " dead" in any case
        out: dict[str, bool] = {}
        for i in range(mark, len(self.log)):
            out[self.log[i]] = self.log[i] in self.defd
        out[" dead"] = " dead" in self.defd
        return out

    def fold(self) -> None:
        # a break leaves the innermost loop, a while True, in the state here: bjoin keeps what
        # the states at its breaks have in common, for the keys where that is not their state
        # where the loop began. Only the keys changed since the last break need a look: the
        # others are as they were there, so what they have in common stays
        for k in self.bnew:
            v = k in self.defd and (not self.bany or (self.bjoin[k] if k in self.bjoin else self.bwas[k]))
            if v != self.bwas[k]:
                self.bjoin[k] = v
            elif k in self.bjoin:
                del self.bjoin[k]
        self.bnew = {}
        self.bany = True

    def join(self, other: dict[str, bool], mark: int) -> None:
        # another path reaches here, in the state since(mark) gave for it: a name stays assigned
        # if it is on both paths (or on the one that is not dead)
        if other[" dead"]:
            return
        if " dead" in self.defd:
            # only the other path goes on: the state at mark, changed as it changed it
            self.undo(mark)
            for k in other:
                if other[k]:
                    self.put(k)
                else:
                    self.drop(k)
            return
        pre: dict[str, bool] = {}
        for i in range(mark, len(self.log)):
            if self.log[i] not in pre:
                pre[self.log[i]] = self.was[i]
        end = len(self.log)
        for k in other:
            if not other[k]:
                self.drop(k)
        for k in pre:
            if not pre[k] and k not in other:
                self.drop(k)
        # the log since mark keeps one entry for each key not in its state at mark: the changes
        # that cancel out (a key assigned on this path alone) are not looked at again by the
        # joins of the enclosing ifs (an elif chain would cost its length times its last branch)
        for i in range(end, len(self.log)):
            if self.log[i] not in pre:
                pre[self.log[i]] = self.was[i]
        n = mark
        for k in pre:
            if (k in self.defd) != pre[k]:
                self.log[n] = k
                self.was[n] = pre[k]
                n += 1
        while len(self.log) > n:
            self.log.pop()
            self.was.pop()


# ---------------------------------------------------------------- code generator
class Gen:
    def __init__(self):
        self.classes: dict[str, ClassInfo] = {}
        self.selfcls = ""  # the class whose method or fields are being declared: what typing.Self is
        self.funcs: dict[str, FnInfo] = {}
        self.aliases: dict[str, str] = {}
        self.imports: dict[str, str] = {}
        self.fglobals: dict[str, bool] = {}
        self.mvars: dict[str, bool] = {}  # module-level variables, also those functions assign
        self.gtypes: dict[str, str] = {}
        self.globs: list[str] = []
        self.gcroots: list[str] = []
        self.consts: list[str] = []
        self.strs: dict[str, str] = {}
        self.strvals: list[str] = []  # the text of each @s.N
        # the runtime functions declared, by RUNTIME key, in the order of their first use (which
        # the program's declare lines keep)
        self.rtfns: dict[str, RtFn] = {}
        self.opfxs: dict[str, int] = {}  # the effects of each op of IROPS but raw, rt, call and init
        for op in IROPS:
            self.opfxs[op] = fxmask(IROPS[op].replace("T", "").replace("*", ""))
        self.out: list[str] = []
        self.fns: list[IFn] = []  # the functions compiled, in the order they were completed
        self.fll: dict[str, int] = {}  # and their positions there by symbol, once the program is built
        self.ltype: dict[str, str] = {}
        self.lreg: dict[str, str] = {}
        self.gdecl: dict[str, bool] = {}
        self.assigned: dict[str, bool] = {}
        self.compvars: dict[str, int] = {}
        self.loops: list[Loop] = []  # the loops the code being compiled is in, innermost last
        self.exits: list[Exit] = []  # what break, continue and return must do on their way out, innermost last
        self.wdepth: list[int] = []  # len(exits) when each enclosing loop began
        self.handler = ""  # the landing block of the innermost try statement around the code, or ""
        self.excs: list[Val] = []  # the exceptions being handled by the except clauses around it (bare raise)
        self.carried = Val("", "")  # a return's value while leave() runs the finally blocks it leaves
        # the names of except ... as clauses around it that have a variable of their own (another
        # type than the name has outside): [name, its type outside ("": a global), register, flag]
        self.shadows: list[list[str]] = []
        self.xcls: dict[str, bool] = {}  # exception classes whose objects are made: they get an ExcClass
        self.eh = False  # the program has a try statement (closed world): exceptions are on (pys_eh_on)
        self.lcs: list[str] = []
        self.lct: list[str] = []
        self.ret = "None"
        self.retann = False
        self.nn: dict[str, bool] = {}
        self.selfname = ""
        self.lazy: dict[str, FnInfo] = {}
        self.lazyat: dict[str, int] = {}  # each lazy function's position in lazy, once it is complete
        self.wake: list[int] = []  # a min-heap of the positions of those called and not yet compiled
        self.called: dict[str, bool] = {}
        self.gflag: dict[str, bool] = {}
        self.ocls: dict[str, int] = {}  # classes that appear inside containers: id in descriptors
        self.lenient = False
        self.uflags: dict[str, bool] = {}
        self.lflag: dict[str, str] = {}
        self.modlevel = False
        self.n = 0
        self.cur = "entry"
        self.term = False
        self.line = 0
        self.curfn = FnInfo("<module>", "@main.init", mk("block", "", 0, []), "")
        self.fn = IFn(self.curfn)  # the function being built
        self.blk: Blk = self.fn.blocks[0]  # and its block that code goes to
        # parameters of a template's function whose argument is None, and the line from which one
        # may hold a value of another type: its first binding (none_ends), once compiled the line
        # that gives it that value (see assign, static_type)
        self.nonevars: dict[str, int] = {}
        # optional locals (and parameters) known not to be None here, as mypy narrows them: a read
        # of one has the type it holds (see narrows)
        self.narrowed: dict[str, bool] = {}
        self.nonecmp = False  # the read being compiled is compared with None (see none_type)
        self.anyopt = False  # a local of an optional type exists: narrows has something to look for
        self.building: dict[str, bool] = {}  # the functions being compiled
        self.wide: dict[str, bool] = {}  # optional values read from a global or a field (function + register), which no test narrows
        self.soft = Node("", "", 0)  # a display compared with a value: what it holds widens the type expected of it (see wider)
        self.retseen: dict[str, bool] = {}  # templates' functions a call used the return type of while they were compiled
        self.branch = 0  # how many if branches and loop bodies enclose the code being compiled
        self.making: list[str] = []  # the template functions being compiled, each with its call site
        self.unsupported: dict[str, str] = {}  # classes of imported modules that cannot be compiled: why
        self.cnodes: dict[int, Node] = {}  # every module-level class or subclass statement, by line
        self.hooks: dict[str, str] = {}  # see hook()
        self.chooks: dict[int, str] = {}
        self.flagged: dict[str, bool] = {}  # globals whose "is assigned" flag effect() reads
        self.noneglobals: dict[str, bool] = {}  # module globals of imported modules that are always None
        # an imported module's globals (and defs and classes) that other code may find unbound:
        # not assigned on every path through its module code, or before an import that may run
        # code calling back into the module
        self.late: dict[str, bool] = {}
        self.lib = False  # declaring an imported module's function: what it cannot compile is an error only where it is called
        self.deps: dict[str, str] = {}  # the modules each module's top-level code imports, space-separated
        self.comp: dict[str, str] = {}  # each module's strongly connected component of that graph (one of its modules)
        self.flowmod = ""
        self.elsekids: list[Node] = []  # the body of a for/while ... else loop being compiled
        self.elsebrk = ""  # and the label after its else block
        self.brks: list[list[dict[str, bool]]] = []  # for each loop being compiled, what narrowed holds at its breaks
        self.elsebrks: list[dict[str, bool]] = []  # those of the last loop with an else block
        # empty [] and {} assigned to a variable without a type: its type has "?" until a use shows
        # what the container holds (see fill). The op that makes one holds a hole, which gets that
        # type (lowering prints a dict's key kind from it)
        self.allowq = False  # the read being compiled may see such a type (len(), a truth test)
        self.lkk: dict[str, str] = {}  # a local's holes, space-separated
        self.gkk: dict[str, str] = {}  # a global's
        self.holes: list[str] = [""]  # each hole's type, "" until a use shows it (0: no hole)
        # globals that hold the same empty container (X = Y at module level), one type: each one's
        # class of twins (named by a member), and each class's members
        self.twin_of: dict[str, str] = {}
        self.twin_set: dict[str, list[str]] = {}
        self.origin: dict[str, str] = {}  # X -> Y for those, where an annotation of the container belongs
        # code compiled before module code assigns what it reads (a template's function called
        # early, a function compiled early for a global's type: see ahead and early)
        self.inits: dict[str, FnInfo] = {}  # each module's top-level code, by module name
        self.mfile: dict[str, str] = {}  # each module's file, by module name
        self.compiled: dict[str, bool] = {}  # the functions compiled so far, by their LLVM name
        self.busy: dict[str, bool] = {}  # the globals ahead() is typing
        self.pending: dict[str, bool] = {}  # default values' globals declared before their def or class statement
        # compiling a from-import of a global its module may leave unbound when the import runs:
        # CPython would raise ImportError, with the module's path, and Pystachy raises AttributeError,
        # so the global must have its type already (no ahead, early or twins)
        self.copying = False
        self.live = False  # fills skips the loops over the empty tuple too (see unfilled)
        self.dead = False  # and found a fill there, or in a branch a static test removes
        self.whole = 0  # static() for the if at this line that fills searches, -1 for none_ends
        self.unsure = False  # and a type not known yet left the test undecided (see static_type)
        # a template's function returning such an empty container without a type (see retval):
        # the locals it returns so, space-separated, by its LLVM name, and the functions whose
        # return type of that kind a call has used, so that it can no longer change (see adopt)
        self.qret: dict[str, str] = {}
        self.qused: dict[str, bool] = {}
        self.inited: dict[str, bool] = {}  # the modules whose top-level code is compiled
        self.guessed: dict[str, str] = {}  # by function: why such a container is list[int] or dict[int, int] there, for a type error
        self.nts: dict[str, bool] = {}  # the typing.NamedTuple classes: a dataclass whose fields cannot be assigned (see nt_class)
        # "C.x": class attribute x of plain class C, which the program assigns through the class
        # (C.x = v, cls.x += 1): a global that objects read until they assign x (see cvar_stores)
        self.cvars: dict[str, bool] = {}
        self.typevars: list[str] = []  # module globals bound to typing.TypeVar(...), which only annotations may name

    # ---- emission helpers
    def err(self, msg: str) -> None:
        if len(self.making) > 0:
            # an error in a template's function: say which call made it compile
            for i in range(len(self.making) - 1, -1, -1):
                msg += ("; " if i < len(self.making) - 1 else " (") + self.making[i]
            msg += ")"
        fail(optnames(msg) if "opt[" in msg else msg, self.line)

    def save(self) -> Frame:
        fr = Frame(self.curfn, self.fn, self.blk)
        fr.ltype = self.ltype
        fr.lreg = self.lreg
        fr.gdecl = self.gdecl
        fr.assigned = self.assigned
        fr.compvars = self.compvars
        fr.loops = self.loops
        fr.exits = self.exits
        fr.wdepth = self.wdepth
        fr.handler = self.handler
        fr.excs = self.excs
        fr.shadows = self.shadows
        fr.lcs = self.lcs
        fr.lct = self.lct
        fr.ret = self.ret
        fr.retann = self.retann
        fr.nn = self.nn
        fr.selfname = self.selfname
        fr.uflags = self.uflags
        fr.lflag = self.lflag
        fr.nonevars = self.nonevars
        fr.narrowed = self.narrowed
        fr.lkk = self.lkk
        fr.branch = self.branch
        fr.modlevel = self.modlevel
        fr.lenient = self.lenient
        fr.n = self.n
        fr.cur = self.cur
        fr.term = self.term
        fr.line = self.line
        return fr

    def restore(self, fr: Frame) -> None:
        self.curfn = fr.curfn
        self.fn = fr.fn
        self.blk = fr.blk
        self.ltype = fr.ltype
        self.lreg = fr.lreg
        self.gdecl = fr.gdecl
        self.assigned = fr.assigned
        self.compvars = fr.compvars
        self.loops = fr.loops
        self.exits = fr.exits
        self.wdepth = fr.wdepth
        self.handler = fr.handler
        self.excs = fr.excs
        self.shadows = fr.shadows
        self.lcs = fr.lcs
        self.lct = fr.lct
        self.ret = fr.ret
        self.retann = fr.retann
        self.nn = fr.nn
        self.selfname = fr.selfname
        self.uflags = fr.uflags
        self.lflag = fr.lflag
        self.nonevars = fr.nonevars
        self.narrowed = fr.narrowed
        self.lkk = fr.lkk
        self.branch = fr.branch
        self.modlevel = fr.modlevel
        self.lenient = fr.lenient
        self.n = fr.n
        self.cur = fr.cur
        self.term = fr.term
        self.line = fr.line

    def tmp(self) -> str:
        self.n += 1
        return f"%t{self.n}"

    def label(self) -> str:
        self.n += 1
        return f"L{self.n}"

    def emit(self, s: str) -> None:
        self.add(Ins("raw", "", s))

    def add(self, i: Ins) -> None:
        # code after a terminator (dead code) goes to a block of its own
        if self.term:
            self.place(self.label())
        self.blk.code.append(i)

    def put(self, i: Ins, k: int) -> None:
        # add i, which defines k values, numbered as k separate instructions would have been
        self.n += 1
        i.r = [self.n]
        self.add(i)
        for _ in range(k - 1):
            self.n += 1
            i.r.append(self.n)

    def ins(self, s: str) -> str:
        r = self.tmp()
        i = Ins("raw", "", f"{r} = {s}")
        i.k = self.n
        self.add(i)
        return r

    def place(self, l: str) -> None:
        if not self.term:
            self.jump(l)
        self.blk = Blk(l)
        self.blk.handler = self.handler
        self.fn.blocks.append(self.blk)
        self.cur = l
        self.term = False

    def jump(self, l: str) -> None:
        i = Ins("br", "", "")
        i.b = [l]
        self.blk.code.append(i)

    def br(self, l: str) -> None:
        if not self.term:
            self.jump(l)
            self.term = True

    def cbr(self, c: str, a: str, b: str) -> None:
        i = Ins("cbr", "", "")
        i.a = [Val(c, "bool")]
        i.b = [a, b]
        self.add(i)
        self.term = True

    def ret_(self, v: Val) -> None:
        # return v (of type None: return nothing)
        i = Ins("ret", "", "")
        if v.t != "None":
            i.a = [v]
        self.add(i)
        self.term = True

    def returned_none(self) -> bool:
        # has the template's function being compiled returned None before it was known what it
        # returns (a ret.none op)
        for b in self.fn.blocks:
            for x in b.code:
                if x.op == "ret.none":
                    return True
        return False

    def unreachable(self) -> None:
        self.add(Ins("unreachable", "", ""))
        self.term = True

    def incoming(self, ph: Ins, v: str, l: str) -> None:
        # the value v of phi ph when control comes from block l
        if len(ph.b) == 0:
            ph.a = []
            ph.b = []
        ph.a.append(Val(v, ph.t))
        ph.b.append(l)

    def phi(self, ph: Ins) -> str:
        self.put(ph, 1)
        return f"%t{ph.r[0]}"

    def select(self, c: str, x: Val, y: Val) -> str:
        # c ? x : y, where x and y have the same type
        i = Ins("select", x.t, "")
        i.a = [Val(c, "bool"), x, y]
        self.put(i, 1)
        return f"%t{i.r[0]}"

    def rt(self, name: str, ret: str, args: list[str]) -> str:
        # an rt op: a call of runtime function name (its LLVM symbol), whose LLVM result type is
        # ret, with args "<LLVM type> <value>", which must be what its RUNTIME entry says
        k = self.runtime(name)
        ts = self.rtfns[k].sig
        ll = self.rtfns[k].ll
        ok = ret == ll[0] and len(args) == len(ll) - 1
        i = Ins("rt", ts[0], k)
        i.a = []
        for j in range(len(args) if ok else 0):
            sp = args[j].find(" ")
            ok = ok and args[j][:sp] == ll[j + 1]
            v = args[j][sp + 1 :]
            i.a.append(Val(v, ts[j + 1]))
            if ts[j + 1] == "#":
                # the descriptor: a string constant, whose text gives the op its static type (and so U?)
                if not v.startswith("@s."):
                    fail(f"internal error: {name} called with the descriptor {v}, which is no string constant", 0)
                i.x = self.strvals[int(v[3:])]
        if not ok:
            fail(f"internal error: {name} called as {ret} ({', '.join(args)}), but RUNTIME declares it as {self.rtfns[k].decl}", 0)
        if ret == "void":
            self.add(i)
            return ""
        self.put(i, 1)
        return f"%t{i.r[0]}"

    def runtime(self, name: str) -> str:
        # declare runtime function name (its LLVM symbol) from its RUNTIME entry; its key
        if name not in RTSYM:
            fail(f"internal error: no RUNTIME entry for {name}", 0)
        k = RTSYM[name]
        if k not in self.rtfns:
            self.rtfns[k] = RtFn(k)
        return k

    def hole(self, kind: str) -> Ins:
        # a new list or dict (kind) whose type a later use decides: the op holds a new hole
        i = Ins("rt", f"{kind}[?]" if kind == "list" else "dict[?,?]", f"{kind}.new")
        i.a = [Val("0", "int")]  # (a dict's key kind: the hole's, when it is lowered)
        if kind == "dict":
            i.a.append(Val("0", "int"))
        i.k = len(self.holes)
        self.holes.append("")
        self.runtime(f"pys_{kind}_new")
        self.put(i, 1)
        return i

    def checked(self, op: str, a: str, b: str) -> list[str]:
        # [result, overflowed] of 64-bit a op b (op: + - *), from llvm.s<op>.with.overflow.i64
        self.runtime(f"llvm.{CHECKED[op]}.with.overflow.i64")
        i = Ins("ovf", "int", op)
        i.a = [Val(a, "int"), Val(b, "int")]
        self.put(i, 3)  # (the call's {i64, i1}, then the two extractvalues)
        return [f"%t{i.r[1]}", f"%t{i.r[2]}"]

    def guard(self, bad: str, msg: str) -> None:
        # if bad, jump to a block (one per function and message) that raises msg ("Kind: text"); in a
        # try statement, one per function, message and landing block (whose key the check holds in x)
        key = msg if self.handler == "" else f"{self.handler} {msg}"
        if key not in self.fn.cold:
            self.fn.cold[key] = self.label()
            if self.handler != "":
                self.fn.coldh[key] = self.handler
        l = self.label()
        i = Ins("check", "", msg)
        if self.handler != "":
            i.x = key
        i.a = [Val(bad, "bool")]
        i.b = [l]
        self.add(i)
        self.term = True
        self.place(l)

    def iop(self, op: str, a: str, b: str) -> str:
        # checked 64-bit arithmetic (op: + - *): overflow raises OverflowError (CPython would grow the int)
        r = self.checked(op, a, b)
        self.guard(r[1], "OverflowError: integer result does not fit in 64 bits")
        return r[0]

    def notnone(self, v: Val, msg: str) -> None:
        # objects may be None (null); using one that is raises like CPython
        if v.t in self.classes and v.v not in self.nn:
            self.guard(self.ins(f"icmp eq ptr {v.v}, null"), msg)

    def unwrap(self, v: Val, msg: str) -> Val:
        # an optional value used where only the type it holds works: None raises msg ("Kind: text")
        if not is_opt(v.t):
            return v
        self.guard(self.ins(f"icmp eq ptr {v.v}, null"), msg)
        return self.deref(v)

    def deref(self, v: Val) -> Val:
        # an optional value known not to be None, as the value it holds: the same pointer, or an
        # int's, float's or bool's box read
        if not is_sopt(v.t):
            return Val(v.v, unopt(v.t))
        return self.from_slot(self.ins(f"load i64, ptr {v.v}"), unopt(v.t))

    def reboxes(self, a: str, b: str) -> bool:
        # is tuple type a tuple type b, but for items that are ints, floats or bools where b's may
        # be None (boxed), and that are as they are otherwise
        if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)) or a == b:
            return False
        for i in range(len(targs(a))):
            x = targs(a)[i]
            y = targs(b)[i]
            if not self.widens(x, y) and not (is_sopt(y) and x == unopt(y)) and not self.reboxes(x, y):
                return False
        return True

    def convert_at(self, v: Val, t: str, label: str) -> Val:
        # v as a t, computed at the end of block label (before its terminator), where it reaches a
        # phi from: an int boxed as an int | None, or an int | None known not to be None unboxed
        if not self.converts(v.t, t):
            return self.coerce(v, t)  # (no code)
        for b in self.fn.blocks:
            if b.label == label:
                return self.convert_in(v, t, b)
        fail(f"internal error: no block {label} to convert {v.t} to {t} in", 0)
        return v

    def converts(self, a: str, b: str) -> bool:
        # does a value of type a take code to be one of type b (convert_in)
        return self.boxes(a, b) or (is_sopt(a) and b == unopt(a))

    def boxes(self, a: str, b: str) -> bool:
        # is a value of type a one of type b once boxed: an int as an int | None, also as tuple items
        return (is_sopt(b) and a == unopt(b)) or self.reboxes(a, b)

    def convert_in(self, v: Val, t: str, blk: Blk) -> Val:
        # v as a t, at the end of block blk, which has ended (see convert_at)
        here = self.blk
        cur = self.cur
        term = self.term
        self.blk = blk
        last = blk.code.pop()
        self.cur = blk.label
        self.term = False
        r = self.deref(v) if is_sopt(v.t) and t == unopt(v.t) else self.coerce(v, t)
        blk.code.append(last)
        self.blk = here
        self.cur = cur
        self.term = term
        return r

    def sconst(self, s: str) -> str:
        if s in self.strs:
            return self.strs[s]
        name = f"@s.{len(self.strs)}"
        self.strs[s] = name
        self.strvals.append(s)
        n = len(s) + 1
        self.consts.append(f'{name} = private unnamed_addr constant {{i64, [{n} x i8]}} {{i64 {n - 1}, [{n} x i8] c"{llstr(s)}\\00"}}, align 8')
        return name

    def alloca(self, t: str, name: str) -> str:
        if t == "None":
            self.err(f"cannot infer the type of '{name}' from None; annotate it ({name}: T | None = None)")
        if t == "":
            self.err(f"cannot infer the type of '{name}'; add a type annotation")
        self.n += 1
        r = f"%{name or 'h'}.{self.n}"
        self.anyopt = self.anyopt or is_opt(t)
        i = Ins("slot", t, name)
        i.r = [self.n]
        self.fn.slots.append(i)
        if name != "":
            self.ltype[name] = t
            self.lreg[name] = r
            if name in self.uflags and name not in self.compvars:
                # "is assigned" flag for a local that some read may find unassigned
                self.lflag[name] = f"%{name}.def.{self.n}"
                i = Ins("slot", "bool", name)
                i.k = 1
                i.r = [self.n]
                self.fn.slots.append(i)
        return r

    # ---- value conversions
    def to_slot(self, v: Val) -> str:
        if v.t == "int":
            return v.v
        if v.t == "float":
            return self.ins(f"bitcast double {v.v} to i64")
        if v.t == "bool":
            return self.ins(f"zext i1 {v.v} to i64")
        return self.ins(f"ptrtoint ptr {v.v} to i64")

    def from_slot(self, s: str, t: str) -> Val:
        if t == "int":
            return Val(s, t)
        if t == "float":
            return Val(self.ins(f"bitcast i64 {s} to double"), t)
        if t == "bool":
            return Val(self.ins(f"trunc i64 {s} to i1"), t)
        return Val(self.ins(f"inttoptr i64 {s} to ptr"), t)

    def rarg(self, v: Val) -> str:
        if v.t == "bool":
            return "i64 " + self.ins(f"zext i1 {v.v} to i64")
        return f"{lt(v.t)} {v.v}"

    def rres(self, r: str, t: str) -> Val:
        if t == "None":
            return Val("null", "None")
        if t == "bool":
            return Val(self.ins(f"icmp ne i64 {r}, 0"), "bool")
        return Val(r, t)

    def as_int(self, v: Val) -> Val:
        if v.t == "bool":
            return Val(self.ins(f"zext i1 {v.v} to i64"), "int")
        return v

    def as_float(self, v: Val) -> Val:
        if v.t == "int":
            return Val(self.ins(f"sitofp i64 {v.v} to double"), "float")
        if v.t == "bool":
            return Val(self.ins(f"uitofp i1 {v.v} to double"), "float")
        return v

    def is_dc(self, t: str) -> bool:
        return t in self.classes and (len(self.classes[t].node.kids) > 1 or t in self.nts)

    def isnum(self, t: str) -> bool:
        return t == "int" or t == "float" or t == "bool"

    def isref(self, t: str) -> bool:
        return t == "None" or lt(t) == "ptr"

    def coerce(self, v: Val, t: str, what: str = "") -> Val:
        # v as a value of type t; what names v for the error when v may be None and t may not
        if v.t == t:
            return v
        if v.t == "None" and t in self.classes:
            return Val("null", t)
        if v.t in self.classes and t in self.classes and self.classes[v.t].exc != "" and self.derives(v.t, t):
            return Val(v.v, t)  # (an exception object is an object of its base classes too)
        if v.t in self.classes and t == "exc" and self.classes[v.t].exc != "":
            self.err(f"expected a builtin exception, got an object of {short(v.t)} (annotate it with {short(v.t)} or a base class of the program)")
        if v.t == "exc" and t in self.classes and self.classes[t].exc != "":
            self.err(f"expected an object of {short(t)}, got a builtin exception, which is not converted to a class of the program (catch it as one: except {short(t)} as e)")
        if self.widens(v.t, t):
            return Val(v.v, t)
        if is_sopt(t) and v.t == unopt(t):
            return Val(self.rt("pys_box", "ptr", ["i64 " + self.to_slot(v)]), t)  # (a new box)
        if self.reboxes(v.t, t):
            # a tuple with an int where t holds an int | None (also deeper): a new tuple, of boxes
            return self.tuple_([self.coerce(self.tget(v, i), targs(t)[i], what) for i in range(len(targs(t)))])
        if is_opt(v.t) and self.widens(unopt(v.t), t):
            # (CPython would pass the None on: there is nothing here that could hold it)
            if what == "":
                what = "a value used as " + typestr(t)
            if self.curfn.ll + v.v in self.wide:
                self.err(f"{what} may be None ({typestr(v.t)}), and a test does not narrow a global or a field (a call may change it): copy it to a local variable, and test that")
            self.err(f"{what} may be None ({typestr(v.t)}); test it with 'is not None' first")
        hint = " (write a float literal like 1.0, or use float())" if t == "float" and v.t == "int" else ""
        if hint == "" and self.curfn.ll in self.guessed:
            hint = f" (perhaps because {self.guessed[self.curfn.ll]})"
        self.err(f"expected {typestr(t)}, got {typestr(v.t)}{hint}")
        return v

    def desc(self, t: str, use: str) -> str:
        # type descriptor for the runtime's generic repr (use "repr"), equality ("==") or ordering
        # ("<", ">", ...; a list or tuple compares its items with == first)
        if t == "int":
            return "i"
        if t == "float":
            return "f"
        if t == "bool":
            return "b"
        if t == "str":
            return "s"
        if is_opt(t) and t != NONEVAR:
            return "?" + self.desc(unopt(t), use)  # None or the value
        if t == "None":
            return "?s"  # (always None: a tuple's item)
        sub = use if use == "repr" or use == "==" else "== " + use
        if is_list(t):
            return "L" + self.desc(elem(t), sub)
        if is_dict(t):
            a = targs(t)
            return "D" + self.desc(a[0], use) + self.desc(a[1], use if use == "repr" else "==")
        if is_tuple(t):
            a = targs(t)
            if len(a) > 9:
                self.err("tuples are limited to 9 elements")
            return "T" + str(len(a)) + "".join([self.desc(x, sub) for x in a])
        if t == "exc":
            return "E"  # (repr: pys_exc_repr; equality: identity)
        if t in self.classes:
            # O<id>: the runtime calls back into pys_obj_eq/cmp/repr, which dispatch on the id, and
            # so the methods of use (a < b: __lt__, else the reflected __gt__) with objects of
            # class t (see obj_helpers): one that cannot take them is an error here
            ms = self.classes[t].methods
            for op in use.split():
                m = "__repr__" if op == "repr" else DUNDER[op]
                m = DUNDER[REFL[op]] if m not in ms and op in REFL else m
                f = ms[m] if m in ms else None
                if f is not None and (f.bad != "" or (op != "repr" and f.ptypes[1] != t)):
                    self.err(f.bad if f.bad != "" else f"comparing {shown(t)} objects (in a list, tuple, in, count, index, sort, min or max) calls {m}() with a {shown(t)}, but it takes a {typestr(f.ptypes[1])}")
            if t not in self.ocls:
                self.ocls[t] = len(self.ocls)
            return f"O{self.ocls[t]:03d}"
        self.err(f"{tname(t)} values cannot be compared or printed")
        return ""

    # ---- types and declarations
    def typeof(self, n: Node) -> str:
        t = self.ann(n)
        if t.startswith("!"):
            self.err(t[1:])
        return t

    def ann(self, n: Node) -> str:
        # the type annotation n denotes, or "!" and why Pystachy does not support it (typeof's error,
        # which a declaration in an imported module defers to where the program uses it)
        k = n.kind
        if k == "None":
            return "None"
        if k == "str":
            return self.ann(self.parse_expr(n.s))
        s = n.s
        if k == "name":
            if s == "int" or s == "float" or s == "bool" or s == "str" or s in self.classes:
                return s
            if is_excname(s):
                return "exc"  # (a builtin exception class: any exception, not only those of the class)
            t = self.typing_name(s)
            if t == "TextIO" or t == "Self" or t.startswith("!"):
                return "file" if t == "TextIO" else self.self_type() if t == "Self" else t
            if s in self.unsupported:
                return "!" + self.unsupported[s]
            if s in self.typevars:
                return f"!TypeVar '{short(s)}'{TYPEVAR}"
        elif k == "attr" and self.typing_attr(n) == "TextIO":
            return "file"
        elif k == "attr" and self.typing_attr(n) == "Self":
            return self.self_type()
        elif k == "binop" and n.s == "|" and self.has_path(n):
            return self.path_union(self.union_members(n, []))
        elif k == "binop" and n.s == "|" and n.kids[1].kind == "None":
            return self.opt(self.ann(n.kids[0]))
        elif k == "binop" and n.s == "|" and n.kids[0].kind == "None":
            return self.opt(self.ann(n.kids[1]))  # None | T
        elif k == "index" and (n.kids[0].kind == "name" or n.kids[0].kind == "attr"):
            base = n.kids[0].s
            if n.kids[0].kind == "attr":
                base = self.typing_attr(n.kids[0]).lower()  # typing.List[int]
            elif base != "list" and base != "dict" and base != "tuple":
                base = self.typing_name(base)
                if base.startswith("!"):
                    return base
                base = base.lower()
            if base == "mapping" or base == "mutablemapping":
                base = "dict"  # (collections.abc's and typing's: what a dict is)
            elif base == "sequence" or base == "mutablesequence":
                base = "list"
            elif base == "classvar":
                return "!" + CLASSVAR
            a: list[Node] = n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]
            if base == "union" and len([x for x in a if self.pathlike(x)]) > 0:
                return self.path_union(a)
            ts: list[str] = []
            for x in a:
                ts.append(self.ann(x))
                if ts[-1].startswith("!"):
                    return ts[-1]
            if base == "list" and len(ts) == 1:
                return f"list[{ts[0]}]"
            if base == "dict" and len(ts) == 2:
                return f"dict[{ts[0]},{ts[1]}]" if key_problem(ts[0]) == "" else "!" + key_problem(ts[0])
            if base == "tuple" and (len(ts) > 0 or n.kids[1].kind == "tuple"):
                return f"tuple[{','.join(ts)}]"  # (tuple[()] is the empty tuple's)
            if base == "optional" and len(ts) == 1:
                return self.opt(ts[0])
            if base == "union":
                us: list[str] = []  # (Union[int, int, None] is Optional[int], as typing collapses it)
                for t in ts:
                    if t not in us:
                        us.append(t)
                if len(us) == 1:
                    return us[0]  # Union[T]
                if len(us) == 2 and (us[0] == "None" or us[1] == "None"):
                    return self.opt(us[0] if us[1] == "None" else us[1])  # Union[T, None]
        if self.typing_ref(n) == "Final":
            return "!a bare Final needs a value to give its type (x: Final = v, a constant in a class body); write Final[T]"
        if self.pathlike(n):
            return "!" + PATHLIKE
        return "!unsupported type annotation"

    def self_type(self) -> str:
        # typing.Self: the class of the method or field it annotates (there is no inheritance)
        c = self.selfcls if self.selfcls != "" else self.curfn.cls
        return c if c != "" else "!typing.Self is only supported in a class, for its methods and fields"

    def pathlike(self, n: Node) -> bool:
        # is annotation n os.PathLike or os.PathLike[T]
        if n.kind == "str":
            n = self.parse_expr(n.s)
        return self.imported_ref(n.kids[0] if n.kind == "index" else n) == "os.PathLike"

    def imported_ref(self, n: Node) -> str:
        # what a name or an attribute chain on one refers to through the imports ("os.fspath"), or ""
        p = ""
        while n.kind == "attr":
            p = "." + n.s + p
            n = n.kids[0]
        return self.imported(n.s + p) if n.kind == "name" else ""

    def union_members(self, n: Node, out: list[Node]) -> list[Node]:
        # the members of a union annotation A | B | ..., in order
        if n.kind == "binop" and n.s == "|":
            self.union_members(n.kids[0], out)
            self.union_members(n.kids[1], out)
        else:
            out.append(n)
        return out

    def has_path(self, n: Node) -> bool:
        return any(self.pathlike(x) for x in self.union_members(n, []))

    def path_union(self, ms: list[Node]) -> str:
        # the type of a union (members ms) that holds os.PathLike, which is dropped: a value of
        # another path type cannot exist in Pystachy, so str | os.PathLike[str] is a str (and with
        # None, str | None), or "!" and the error
        s = False
        none = False
        for x in ms:
            if not self.pathlike(x):
                t = self.ann(x)
                if t.startswith("!"):
                    return t
                if t != "str" and t != "None" and t != "opt[str]":
                    return "!" + PATHLIKE.replace(" with str ", f" with str, not with {typestr(t)} ")
                s = s or t != "None"
                none = none or t != "str"
        return ("opt[str]" if none else "str") if s else "!" + PATHLIKE

    def typevar_def(self, st: Node) -> bool:
        # is st T = TypeVar("T") (typing's or typing_extensions'): T is then a name only annotations use
        if st.kind != "assign" or len(st.kids) != 2 or st.kids[0].kind != "name" or st.kids[1].kind != "call":
            return False
        c = st.kids[1]
        if self.imported_ref(c.kids[0]) != "typing.TypeVar":
            return False
        self.line = st.line
        if len(c.kids) < 2 or c.kids[1].kind != "str":
            self.err("TypeVar() needs the type variable's name, a string, as its first argument")
        for a in c.kids[2:]:
            if a.kind != "kw" or not is_const(a.kids[0]):
                self.err("a TypeVar's constraints, and a bound other than a string, are not supported")
        return True

    def typevar_in(self, anns: list[Node]) -> str:
        # the first TypeVar annotations anns mention (also in a string), or ""
        if len(self.typevars) == 0:
            return ""
        for a in anns:
            if a.kind == "str":
                a = self.parse_expr(a.s)
            if a.kind == "name" and a.s in self.typevars:
                return a.s
            r = self.typevar_in(a.kids)
            if r != "":
                return r
        return ""

    def ann_problem(self, n: Node, ret: bool) -> str:
        # why typeof(n), for a return annotation (ret), or vtype(n) fails, or "" (one that raises
        # where CPython evaluates it is the loader's error: see Loader.deftime)
        t = self.ann(n)
        if t == "None" and not ret:
            return "None is only supported as a return type; annotate an optional value as T | None"
        return t[1:] if t.startswith("!") else ""

    def vtype(self, n: Node) -> str:
        # the annotation of a variable, parameter or field: None alone is only a return type
        why = self.ann_problem(n, False)
        if why != "":
            self.err(why)
        return self.ann(n)

    def typing_attr(self, n: Node) -> str:
        # the typing name an attribute denotes (typing.Optional, t.List after import typing as t), or ""
        p = ""
        while n.kind == "attr":
            p = "." + n.s + p
            n = n.kids[0]
        p = self.imported(n.s + p) if n.kind == "name" else ""
        return p[7:] if p.startswith("typing.") else p[16:] if p.startswith("collections.abc.") else ""

    def typing_ref(self, n: Node) -> str:
        # the typing (or collections.abc) name that a name or attribute n refers to, or "" (no error)
        if n.kind == "attr":
            return self.typing_attr(n)
        if n.kind != "name":
            return ""
        p = self.imported(n.s)
        if p.startswith("typing.") or p.startswith("collections.abc."):
            return p[p.rfind(".") + 1 :]
        return short(n.s) if short(n.s) in TYPING and "__future__.annotations" in self.imports.values() else ""

    def typing_forms(self, m: Mod, body: list[Node], cls: bool) -> list[Node]:
        # what typing decides before any code runs, in the statements of body (a class body if cls)
        # and in those they hold: a def decorated with @overload is a stub that the def after it
        # replaces, so it is dropped (unless no def of its name follows in its block, past other
        # defs, or a default is more than a constant); x: Final = v is x = v outside class bodies,
        # and a field typed by the constant v in one, x: Final[T] is x: T, and x: Final alone does
        # nothing
        out: list[Node] = []
        defs: dict[str, bool] = {}
        for i in range(len(body)):
            st = body[i]
            stub = self.stub(m, st)
            self.line = st.line
            if stub and st.s in defs:
                self.err(f"an @overload stub after the definition of '{short(st.s)}' is not supported (it would replace it)")
            if stub:
                # (one that nothing replaces is what a call finds, which raises NotImplementedError;
                # other defs between them run nothing that could call it)
                j = i + 1
                while j < len(body) and body[j].kind == "def" and (body[j].s != st.s or self.stub(m, body[j])):
                    j += 1
                later = False  # (a def of its name past other statements, which could call the stub first)
                for k in body[j:]:
                    later = later or (k.kind == "def" and k.s == st.s)
                if (j == len(body) or body[j].kind != "def") and m.name != "" and not later:
                    out.append(st)  # (an imported module's, also a method: an error where it is called, see declare_fn)
                    continue
                if j == len(body) or body[j].kind != "def":
                    self.err(STUB.replace("NAME", short(st.s)))
                for p in st.kids[0].kids:
                    if p.kids[1].kind != "ellipsis" and not is_const(p.kids[1]):
                        self.err("a default of an @overload stub that is not a constant (or ...) is not supported (CPython evaluates it where the def runs)")
                continue
            if st.kind == "def":
                defs[st.s] = True
            a = st.kids[1] if st.kind == "annassign" else st
            if a.kind == "index" and self.typing_ref(a.kids[0]) == "Final":
                st.kids[1] = a.kids[1]
            elif a is not st and len(st.kids) == 3 and not cls and self.typing_ref(a) == "Final":
                st.kind = "assign"
                st.kids = [st.kids[0], st.kids[2]]
            elif a is not st and len(st.kids) == 3 and self.typing_ref(a) == "Final":
                # (a field, typed by its constant)
                v = st.kids[2]
                if v.kind == "int" or v.kind == "float" or v.kind == "str":
                    st.kids[1] = mk("name", v.kind, v.line, [])
                elif v.kind == "True" or v.kind == "False":
                    st.kids[1] = mk("name", "bool", v.line, [])
                else:
                    self.err("a field annotated Final without a type needs a constant value (int, float, str or bool): annotate it Final[T]")
            elif a is not st and self.typing_ref(a) == "Final":
                st.kind = "pass"  # (x: Final alone binds nothing)
                st.kids = []
            for k in st.kids:
                if k.kind == "block":
                    k.kids = self.typing_forms(m, k.kids, st.kind == "class")
                elif k.kind == "class":
                    k.kids[0].kids = self.typing_forms(m, k.kids[0].kids, True)  # (a subclass's)
                elif k.kind == "except":
                    k.kids[1].kids = self.typing_forms(m, k.kids[1].kids, False)
            out.append(st)
        return out if len(out) < len(body) else body

    def stub(self, m: Mod, st: Node) -> bool:
        # is st a def decorated with typing.overload
        r = False
        for d in st.kids[3:] if st.kind == "def" else []:
            root = d.s[: d.s.find(".")] if "." in d.s else d.s
            r = r or (self.imported(m.q + root) or self.imported(root)) + d.s[len(root) :] == "typing.overload"
        return r

    def typing_name(self, s: str) -> str:
        # List/Dict/Tuple/Optional/TextIO must come from typing, unless annotations are never
        # evaluated (from __future__ import annotations): the typing name s denotes, "", or "!" and
        # the error
        if self.imported(s).startswith("typing."):
            return self.imported(s)[7:]
        if self.imported(s).startswith("collections.abc."):
            return self.imported(s)[16:]
        if short(s) in TYPING and "__future__.annotations" in self.imports.values():
            return short(s)  # (also a module's name that only an if TYPE_CHECKING: block imports)
        return f"!name '{s}' is not defined (import it from typing)" if s in TYPING else ""

    def opt(self, t: str) -> str:
        # T | None, Optional[T]: a class type includes None already; str, int, float, bool, list,
        # dict and tuple become opt[T] (or "!" and why not)
        if t.startswith("!"):
            return t
        if t == "exc":
            return "!an exception that may be None (Exception | None) is not supported: only an object of an exception class of the program may be None"
        r = self.optional(t)
        return r if r != "" else f"!None/Optional is only supported for {OPTTYPES}, not {typestr(t)}"

    def optional(self, t: str) -> str:
        # the type of a value that is a t or None, "" if there is none
        if t in self.classes or is_opt(t):
            return t
        if (t == "str" or self.isnum(t) or is_list(t) or is_dict(t) or is_tuple(t)) and "?" not in t:
            return f"opt[{t}]"
        return ""

    def join(self, a: str, b: str) -> str:
        # the type of a value that is an a or a b, where None and optional types meet (T and None
        # make T | None), or ""
        if a == b or self.widens(b, a):
            return a
        if self.widens(a, b):
            return b
        if a == "None" or b == "None":
            return self.optional(b if a == "None" else a)
        if is_opt(a) or is_opt(b):
            j = self.join(unopt(a), unopt(b))
            return self.optional(j) if j != "" else ""
        if is_tuple(a) and is_tuple(b) and len(targs(a)) == len(targs(b)):
            js = [self.join(targs(a)[i], targs(b)[i]) for i in range(len(targs(a)))]  # (item by item)
            return f"tuple[{','.join(js)}]" if "" not in js else ""
        return ""

    def wider(self, a: str, b: str) -> str:
        # the type of values of types a and b as they are, where they differ only in what may be
        # None (list[str] and list[str | None]: list[str | None]), for comparisons and for new
        # containers made of both; "" if there is none (an int is no int | None as it is: that is a box)
        if a == b:
            return a
        if self.isnum(a) or self.isnum(b):
            return ""
        if "?" in a or "?" in b:
            return ""
        if a == "None" or b == "None":
            return self.optional(b if a == "None" else a)
        if is_opt(a) or is_opt(b):
            w = self.wider(unopt(a), unopt(b))
            return self.optional(w) if w != "" else ""
        if is_list(a) and is_list(b):
            w = self.wider(elem(a), elem(b))
            return f"list[{w}]" if w != "" else ""
        if is_dict(a) and is_dict(b):
            k = self.wider(targs(a)[0], targs(b)[0])  # (tuple keys whose items may be None)
            w = self.wider(targs(a)[1], targs(b)[1])
            return f"dict[{k},{w}]" if k != "" and w != "" else ""
        if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
            return ""
        bs = targs(b)
        ws: list[str] = []
        for x in targs(a):
            w = self.wider(x, bs[len(ws)])
            if w == "":
                return ""
            ws.append(w)
        return f"tuple[{','.join(ws)}]"

    def boxwider(self, a: str, b: str) -> str:
        # wider(a, b) for tuple types whose items differ also where one is an int, float or bool and
        # the other an int | None, float | None or bool | None: the tuple of the latter, which the
        # tuple that is not optional itself can become (coerce boxes its items); "" if there is none
        if is_opt(a) and is_opt(b):
            return ""
        if is_opt(a) or is_opt(b):
            w = self.boxwider(unopt(a), unopt(b))
            return self.optional(w) if w != "" and unopt(a if is_opt(a) else b) == w else ""
        if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
            return ""
        bs = targs(b)
        ws: list[str] = []
        for x in targs(a):
            y = bs[len(ws)]
            w = self.wider(x, y)
            if w == "" and (is_sopt(y) and x == unopt(y) or y == "None" and self.isnum(x)):
                w = self.optional(x)
            elif w == "" and (is_sopt(x) and y == unopt(x) or x == "None" and self.isnum(y)):
                w = self.optional(y)
            elif w == "":
                w = self.boxwider(x, y)
            if w == "":
                return ""
            ws.append(w)
        return f"tuple[{','.join(ws)}]"

    def boxto(self, v: Val, t: str) -> Val:
        # v as a value of tuple type t = boxwider(v.t, ...), boxing its items where it needs to
        if v.t == t:
            return v
        if is_opt(t) and not is_opt(v.t):
            return Val(self.coerce(v, unopt(t)).v, t)
        return self.coerce(v, t)

    def widens(self, a: str, b: str) -> bool:
        # is a value of type a, as it is, a value of type b: None or T as T | None (or as an object
        # type), an object of an exception class as one of a base class (whose layout its own
        # extends), and a tuple item by item (tuples cannot change, so their items can widen)
        if a == b:
            return True
        if is_opt(b):
            return a == "None" or (not is_sopt(b) and self.widens(unopt(a), unopt(b)))  # (an int | None is a box)
        if b in self.classes:
            return a == "None" or (a in self.classes and self.classes[a].exc != "" and self.derives(a, b))
        if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
            return False
        bs = targs(b)
        i = 0
        for x in targs(a):
            if not self.widens(x, bs[i]):
                return False
            i += 1
        return True

    def declare_fn(self, d: Node, cls: str) -> FnInfo:
        # a function or method. A module-level function with a parameter that has no annotation
        # is a template: a call compiles it, once per list of argument types, for those types
        # (see instance), and what cannot be compiled in it is an error only then
        self.line = d.line
        f = FnInfo(d.s, f"@f.{d.s}" if cls == "" else f"@m.{cls}.{d.s}", d, cls)
        ps = d.kids[0].kids
        deco = ""
        stub = False  # (an imported module's that no def follows: see typing_forms)
        for x in d.kids[3:]:
            if x.s != "async" and deco == "":
                deco = x.s
            stub = stub or self.imported(x.s) == "typing.overload"
        if cls != "" and len(d.kids) == 4 and len(d.kids[3].kids) == 0 and (deco == "staticmethod" or deco == "classmethod"):
            f.deco = deco  # (a method that takes no self, or its class as cls)
        deco = short(deco)
        if deco != "" and f.deco == "" and not self.lib:
            # (CPython applies a decorator when the def runs, called or not: see decorators())
            if deco in TYPING and self.imported(deco) == "" and not self.bound(deco):
                self.err(f"name '{deco}' is not defined (import it from typing)")
            self.err(f"unsupported decorator @{deco}")
        if cls != "" and len(ps) == 0 and f.deco != "staticmethod":
            self.err(f"method '{d.s}' of class '{cls}' must take {'cls' if f.deco != '' else 'self'} as its first parameter")
        tv = self.typevar_in([p.kids[0] for p in ps if p.kind == "param"] + [d.kids[1]])
        if tv != "" and cls == "":
            # def f(x: T) with T = TypeVar("T"): what mentions a TypeVar is left unannotated, as in
            # def f[T](x: T) (a template)
            for p in ps:
                if p.kind == "param" and self.typevar_in([p.kids[0]]) != "":
                    p.kids[0] = mk("noann", "", d.line, [])
            if self.typevar_in([d.kids[1]]) != "":
                d.kids[1] = mk("noann", "", d.line, [])
        tvbad = f"method '{d.s}' of class '{short(cls)}' mentions TypeVar '{short(tv)}', which is not supported: a method is not a template (a module-level function whose parameters mention a TypeVar is, compiled for each call's argument types)"
        if tv != "" and cls != "" and not self.lib:
            self.err(tvbad)
        for i in range(len(ps)):
            if cls == "" and ((ps[i].kind == "param" and ps[i].kids[0].kind == "noann") or ps[i].kind == "starparam"):
                f.generic = True
        marks = d.kids[0].s.split(",")
        bad = ""
        f.npos = -1
        for i in range(len(ps)):
            p = ps[i]
            if i == int(marks[1]):
                f.npos = len(f.params)
            if i == int(marks[0]):
                f.posonly = len(f.params)
            if i == 0 and f.deco == "classmethod" and p.kind == "param":
                continue  # cls: the class, which is not passed (see rename)
            if p.kind == "starparam" and f.generic:
                # *args: each call passes the extra positional arguments as a tuple of their types
                f.vararg = len(f.params)
                f.varelem = self.vtype(p.kids[0]) if p.kids[0].kind != "noann" else ""
                f.params.append(p.s)
                f.defaults.append(mk("noann", "", p.line, []))
                f.dglob.append("")
                f.dtypes.append("")
                f.ptypes.append("")
                continue
            if p.kind != "param":
                bad = "**kwargs is not supported" if p.kind == "dstarparam" else "*args, **kwargs are not supported"
                continue
            f.params.append(p.s)
            f.defaults.append(p.kids[1])
            f.dglob.append("")
            f.dtypes.append("")
            if i == 0 and takes_self(f):
                f.ptypes.append(cls)
            elif p.kids[0].kind == "noann":
                if not f.generic:
                    self.err(f"parameter '{p.s}' of '{d.s}' needs a type annotation")
                f.ptypes.append("")
            elif self.lib and self.ann_problem(p.kids[0], False) != "":
                bad = f"{cls + '.' if cls != '' else ''}{d.s}() is not supported: parameter '{p.s}': {self.ann_problem(p.kids[0], False)}"
                f.ptypes.append("")  # (any type: the def statement evaluates its default, see hoist)
            else:
                f.ptypes.append(self.vtype(p.kids[0]))
        if int(marks[0]) == len(ps) and len(ps) > 0:
            f.posonly = len(f.params)  # def f(a, b, /)
        if f.npos < 0:
            f.npos = len(f.params)
        if f.vararg >= 0:
            f.npos = f.vararg
        if len(d.kids) > 3 and f.deco == "":
            bad = f"unsupported decorator @{deco}" if deco != "" else "async functions are not supported"
            bad = STUB.replace("NAME", short(d.s)) if stub else bad
        if f.deco != "" and d.s.startswith("__") and d.s.endswith("__"):
            bad = f"@{f.deco} on the special method {d.s} is not supported"
        if f.deco == "classmethod" and bad == "" and ps[0].kind == "param":
            # its cls parameter names the class in its body: cls(...) makes one, cls.x reads a
            # class attribute, cls.m(...) calls a static or class method
            asg: dict[str, bool] = {}
            local_names(d.kids[2].kids, asg)
            if ps[0].s in asg:
                bad = f"class method {d.s}() assigns its parameter '{ps[0].s}', which names the class: not supported"
            f.clsuse = mentions(d.kids[2], [ps[0].s])
            if f.clsuse:
                f.orig = clone(d)
            rename(d.kids[2], ps[0].s, cls)
        if bad == "" and has_kind(d.kids[2], "yield"):
            bad = UNSUPPORTED["yield"]  # a generator function
            if cls != "" and d.s == "__iter__":
                bad += ": __iter__ can return iter(xs) of a list xs of the items"
        if bad == "" and self.lib and d.kids[1].kind != "noann":
            it = self.iter_item(d.kids[1]) if cls != "" and d.s == "__iter__" else None  # (see iter_ann)
            why = self.ann_problem(d.kids[1], True) if it is None else self.ann_problem(it, False)
            if why != "":
                bad = f"{cls + '.' if cls != '' else ''}{d.s}() is not supported: return annotation: {why}"
        if tv != "" and cls != "":
            bad = tvbad  # (an imported module's: an error only where it is used)
        if bad != "" and not f.generic and not self.lib:
            self.err(bad)
        f.bad = bad
        if bad != "" and self.lib:
            f.ret = "None"
        elif d.kids[1].kind != "noann" and cls != "" and d.s == "__iter__" and self.iter_ann(d.kids[1]) != "":
            f.ret = self.iter_ann(d.kids[1])
            f.iters = True
        elif d.kids[1].kind != "noann":
            f.ret = self.typeof(d.kids[1])
        elif f.generic:
            f.ret = ""
        return f

    def iter_ann(self, n: Node) -> str:
        # an __iter__'s return annotation Iterator[T] or Iterable[T] (typing's or collections.abc's):
        # list[T], the list that the iterator it returns steps through (see iter_ret); else ""
        t = self.iter_item(n)
        return f"list[{self.vtype(t)}]" if t is not None else ""

    def iter_item(self, n: Node) -> Node:
        # T, of an __iter__'s return annotation Iterator[T] or Iterable[T]; else None
        if n.kind == "str":
            n = self.parse_expr(n.s)
        if n.kind != "index" or (self.typing_ref(n.kids[0]) != "Iterator" and self.typing_ref(n.kids[0]) != "Iterable"):
            return None
        return n.kids[1]

    def exc_attr(self, ci: ClassInfo, name: str) -> None:
        # a field name of class ci that is an attribute of its builtin exception class (EXCATTRS): an
        # error (for an imported module's class, where the program uses it)
        for b in EXCATTRS:
            if ci.exc != "" and name in EXCATTRS[b].split() and exc_derives(ci.exc, b):
                use = "its exit status" if b == "SystemExit" else "its str() and repr()" if b == "BaseException" else "its str()"
                why = f"a field '{name}' of exception class {short(ci.name)} is not supported: it would be {b}'s own attribute {name}, which decides {use}"
                if ci.mod == "":
                    self.err(why)
                ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
        for b in EXCINIT:
            if ci.exc != "" and name in EXCINIT[b].split() and exc_derives(ci.exc, b) and not self.init_after(ci, name) and not self.shadowed(ci, name):
                why = f"a field '{name}' of exception class {short(ci.name)} is not supported here: {b}.__init__() sets its attribute {name} as it runs, after what assigned the field before it (assign self.{name} in __init__, after super().__init__(...))"
                if ci.mod == "":
                    self.err(why)
                ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"

    def shadowed(self, ci: ClassInfo, name: str) -> bool:
        # does class ci or a base of the program give attribute name a default in its class body:
        # then CPython's instances keep it in their __dict__, apart from the slot of the builtin
        # base that its __init__ sets
        c = ci.name
        while c in self.classes:
            for st in self.classes[c].node.kids[0].kids:
                if st.kind == "annassign" and len(st.kids) == 3 and st.kids[0].kind == "name" and st.kids[0].s == name:
                    return True
            c = self.classes[c].base
        return False

    def init_after(self, ci: ClassInfo, name: str) -> bool:
        # is field name of class ci's objects assigned after its builtin base's __init__ runs, if it
        # runs: the __init__ that runs for them (of ci or the nearest base) does not call its base's,
        # or calls it in a statement of its own after which it assigns self.name (or the base's
        # __init__ does so, for its own objects), and calls it nowhere else
        if "__init__" not in ci.methods:
            return False  # (the builtin __init__ runs as the object is made)
        f = ci.methods["__init__"]
        d = self.classes[f.cls]
        me = f.params[0] if len(f.params) > 0 else ""
        body = f.node.kids[2].kids
        last = -1
        for i in range(len(body)):
            st = body[i]
            c = st.kids[0] if st.kind == "expr" else st
            a = c.kids[0] if c.kind == "call" else c
            if a.kind == "attr" and a.s == "__init__" and ((a.kids[0].kind == "call" and a.kids[0].kids[0].kind == "name" and a.kids[0].kids[0].s == "super")
                                                         or (a.kids[0].kind == "name" and len(c.kids) > 1 and c.kids[1].kind == "name" and c.kids[1].s == me)):
                last = i
            elif calls_init(st):
                return False  # (it may call the base's __init__ in another way)
        if last < 0:
            return True
        if d.base in self.classes and self.init_after(self.classes[d.base], name):
            return True
        for st in body[last + 1 :]:
            if (st.kind == "assign" or st.kind == "annassign") and st.kids[0].kind == "attr" and st.kids[0].s == name and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == me:
                return True
        return False

    def add_field(self, ci: ClassInfo, name: str, t: str) -> None:
        if name not in ci.ftypes:
            self.exc_attr(ci, name)
        if name in ci.ftypes:
            if ci.ftypes[name] != t:
                self.err(f"field '{name}' redeclared with a different type")
            return
        ci.fpos[name] = len(ci.fields)
        ci.fields.append(name)
        ci.ftypes[name] = t

    def declare_fields(self, ci: ClassInfo) -> None:
        noann = mk("noann", "", ci.node.line, [])
        last = ""
        if ci.base in self.classes:
            # an exception class's objects begin with its base's fields (and their flags, see fl_fields)
            b = self.classes[ci.base]
            for x in b.fields:
                self.add_field(ci, x, b.ftypes[x])
                if x in b.fdefault:
                    ci.fdefault[x] = b.fdefault[x]
        elif ci.exc != "":
            # what its constructor sets (exc_object): its ExcClass, str(e) and the text between repr(e)'s
            # parentheses, and a SystemExit's status and whether its code is one (None, an int or a bool)
            xs = EXCFIELDS.split()
            for x in xs if exc_derives(ci.exc, "SystemExit") else xs[:3]:
                self.add_field(ci, " " + x[: x.find(":")], x[x.find(":") + 1 :])
        for st in ci.node.kids[0].kids:
            self.line = st.line
            if st.kind == "annassign" and st.kids[0].kind == "name" and ci.base in self.classes and st.kids[0].s in self.classes[ci.base].ftypes:
                # (a class attribute of the base bound again, with the same type: as x = v is)
                b = self.classes[ci.base]
                if len(st.kids) < 3 or st.kids[0].s not in b.fdefault or self.vtype(st.kids[1]) != b.ftypes[st.kids[0].s]:
                    self.err(f"field '{st.kids[0].s}' of '{short(ci.base)}' declared again in '{short(ci.name)}' (not supported" + (", but for a class attribute of the same type" if st.kids[0].s in b.fdefault else "") + ")")
            if st.kind == "annassign" and st.kids[0].kind == "name" and ci.mod != "" and self.ann_problem(st.kids[1], False) != "":
                # an imported module's class: an error only where the program uses it
                ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {self.ann_problem(st.kids[1], False)}"
                self.add_field(ci, st.kids[0].s, "int")
            elif st.kind == "annassign" and st.kids[0].kind == "name":
                self.add_field(ci, st.kids[0].s, self.vtype(st.kids[1]))
                if len(st.kids) == 3:
                    ci.fdefault[st.kids[0].s] = st.kids[2]
                    last = st.kids[0].s
                elif last != "" and ci.name in self.nts:
                    self.err(f"Non-default namedtuple field {st.kids[0].s} cannot follow default field {last}")
                elif last != "" and self.is_dc(ci.name) and not ci.kwonly:
                    self.err(f"non-default argument '{st.kids[0].s}' follows default argument '{last}'")
            elif st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and self.is_dc(ci.name):
                self.err(f"a class attribute without an annotation ({st.kids[0].s} = ...), which is no field of a {'NamedTuple' if ci.name in self.nts else 'dataclass'}, is not supported: annotate it")
            elif st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name":
                # x = v: a class attribute, typed by v as a field is (and from here on read as x: T = v)
                t = self.guess(st.kids[1], FnInfo("", "", ci.node, ""))
                bt = self.classes[ci.base].ftypes.get(st.kids[0].s, "") if ci.base in self.classes else ""
                if t != "" and bt != "" and (self.widens(t, bt) or self.boxes(t, bt)):
                    t = bt  # (a class attribute of the base bound again, with a value of its type)
                if t == "" and ci.mod == "":
                    self.err(f"cannot infer the type of class attribute '{st.kids[0].s}'; annotate it ({st.kids[0].s}: T = ...)")
                if t == "":
                    ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: cannot infer the type of class attribute '{st.kids[0].s}'"
                    t = "int"
                self.add_field(ci, st.kids[0].s, t)
                ci.fdefault[st.kids[0].s] = st.kids[1]
                st.kind = "annassign"
                st.kids = [st.kids[0], mk("noann", "", st.line, []), st.kids[1]]
            elif st.kind != "def" and st.kind != "pass" and not (st.kind == "expr" and (st.kids[0].kind == "str" or st.kids[0].kind == "ellipsis")):
                what = "an assignment to anything but one name (x = v)" if st.kind == "assign" else "an expression statement" if st.kind == "expr" else f"a{'n' if st.kind[0] in 'aeiou' else ''} {st.kind} statement"
                self.err(f"a class body may only contain fields, methods, a docstring, pass and ..., not {what}")
        if ci.name in self.nts:
            self.nt_class(ci)
        if self.is_dc(ci.name):
            self.dc_methods(ci)
        if "__init__" in ci.methods or ci.exc != "":
            # (an exception class without __init__ of its own takes its base's, or none)
            if "__init__" in ci.methods and ci.methods["__init__"].cls == ci.name:
                f = ci.methods["__init__"]
                self.scan_fields(ci, f, f.node.kids[2].kids)
            return
        # synthesize __init__: @dataclass takes every field as a parameter
        body: list[Node] = []
        d = mk("def", "__init__", ci.node.line, [noann, noann, mk("block", "", ci.node.line, body)])
        f = FnInfo("__init__", f"@m.{ci.name}.__init__", d, ci.name)
        me = "self" if "self" not in ci.ftypes else "__pys_self"  # (a field may be named self)
        f.params.append(me)
        f.ptypes.append(ci.name)
        f.defaults.append(noann)
        f.dglob.append("")
        if self.is_dc(ci.name):
            if ci.kwonly:
                f.npos = 1  # (self, and the fields by keyword)
            for fl in ci.fields:
                f.params.append(fl)
                f.ptypes.append(ci.ftypes[fl])
                f.defaults.append(ci.fdefault[fl] if fl in ci.fdefault else noann)
                f.dglob.append("")
                body.append(mk("assign", "", d.line, [mk("attr", fl, d.line, [mk("name", me, d.line, [])]), mk("name", fl, d.line, [])]))
            if "__post_init__" in ci.methods:
                # (then calls __post_init__, as the __init__ @dataclass writes does)
                post = mk("attr", "__post_init__", d.line, [mk("name", me, d.line, [])])
                body.append(mk("expr", "", d.line, [mk("call", "", d.line, [post])]))
        ci.methods["__init__"] = f

    def nt_class(self, ci: ClassInfo) -> None:
        # class P(NamedTuple): a dataclass (its __init__ and __repr__) whose fields are never
        # assigned after __init__, read in order where it is unpacked, indexed or iterated, and
        # compared, concatenated and %-formatted as the tuple of its fields (see ntop); tuple's
        # other methods are not there
        self.line = ci.node.line
        for m in "__new__ __init__ __slots__ __getnewargs__ _fields _field_defaults _make _replace _asdict _source".split():
            if m in ci.methods:
                self.err(f"Cannot overwrite NamedTuple attribute {m}")
        for m in ["__getitem__", "__iter__"]:
            if m in ci.methods:
                self.err(f"a NamedTuple that defines {m} is not supported (Pystachy reads its fields where CPython would call it)")
        for fl in ci.fields:
            if fl.startswith("_"):
                self.err(f"Field names cannot start with an underscore: '{fl}'")
        if len(ci.fields) == 0:
            self.err("a NamedTuple without fields is not supported")

    def nt_base(self, n: Node) -> bool:
        # does a class's base n name typing.NamedTuple
        return (n.kind == "name" and self.imported(n.s) == "typing.NamedTuple") or (n.kind == "attr" and self.typing_attr(n) == "NamedTuple")

    def frozen(self, t: str, name: str) -> None:
        # a NamedTuple's fields are assigned only by its __init__
        if t in self.nts and not (self.curfn.name == "__init__" and self.curfn.cls == t):
            self.err(f"cannot assign to field '{name}' of NamedTuple {short(t)} (AttributeError: can't set attribute); make a new one with _replace({name}=...)")

    def synth(self, ci: ClassInfo, name: str, ret: str, body: list[Node]) -> None:
        # a method the compiler writes for a dataclass, generated only if the program calls it
        line = ci.node.line
        noann = mk("noann", "", line, [])
        f = FnInfo(name, f"@m.{ci.name}.{name}", mk("def", name, line, [noann, noann, mk("block", "", line, body)]), ci.name)
        f.params.append("self")
        f.ptypes.append(ci.name)
        if name == "__eq__":
            f.params.append("other")
            f.ptypes.append(ci.name)
        for _ in f.params:
            f.defaults.append(noann)
            f.dglob.append("")
        f.ret = ret
        ci.methods[name] = f
        self.lazy[f.ll] = f

    def dc_methods(self, ci: ClassInfo) -> None:
        # @dataclass: __repr__ is Name(field=repr(value), ...), __eq__ compares the fields in order
        line = ci.node.line
        me = mk("name", "self", line, [])
        other = mk("name", "other", line, [])
        if "__repr__" not in ci.methods:
            parts: list[Node] = []
            lit = short(ci.name) + "("
            for i in range(len(ci.fields)):
                parts.append(mk("str", lit + (", " if i > 0 else "") + ci.fields[i] + "=", line, []))
                parts.append(mk("call", "", line, [mk("name", "__pys_repr", line, []), mk("attr", ci.fields[i], line, [me])]))
                lit = ""
            parts.append(mk("str", lit + ")", line, []))
            # like reprlib.recursive_repr: an object already being printed shows as ...
            enter = mk("call", "", line, [mk("name", "__pys_repr_enter", line, []), me])
            busy = mk("block", "", line, [mk("return", "", line, [mk("str", "...", line, [])])])
            r = mk("name", "r", line, [])
            if ci.name in self.nts:
                # (a tuple's repr has no guard: a cycle through a field shows where a list's repr stops it)
                self.synth(ci, "__repr__", "str", [mk("return", "", line, [mk("fstr", "", line, parts)])])
            else:
                self.synth(ci, "__repr__", "str", [mk("if", "", line, [mk("unary", "not", line, [enter]), busy, mk("block", "", line, [])]),
                                                  mk("assign", "", line, [r, mk("fstr", "", line, parts)]),
                                                  mk("expr", "", line, [mk("call", "", line, [mk("name", "__pys_repr_leave", line, []), me])]),
                                                  mk("return", "", line, [r])])
        if "__eq__" not in ci.methods and ci.name not in self.nts:  # (a NamedTuple's is tuple's, see ntop)
            test = mk("True", "", line, [])
            for i in range(len(ci.fields)):
                c = mk("cmp", "==", line, [mk("attr", ci.fields[i], line, [me]), mk("attr", ci.fields[i], line, [other])])
                test = c if i == 0 else mk("boolop", "and", line, [test, c])
            same = mk("cmp", "is", line, [other, me])
            yes = mk("block", "", line, [mk("return", "", line, [mk("True", "", line, [])])])
            isnone = mk("cmp", "is", line, [other, mk("None", "", line, [])])
            no = mk("block", "", line, [mk("return", "", line, [mk("False", "", line, [])])])
            self.synth(ci, "__eq__", "bool", [mk("if", "", line, [same, yes, mk("block", "", line, [])]),
                                            mk("if", "", line, [isnone, no, mk("block", "", line, [])]), mk("return", "", line, [test])])

    def scan_fields(self, ci: ClassInfo, f: FnInfo, body: list[Node]) -> None:
        # fields are the attributes assigned on self inside __init__
        for st in body:
            self.line = st.line
            k = st.kind
            if (k == "assign" or k == "annassign") and st.kids[0].kind == "attr" and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == f.params[0]:
                name = st.kids[0].s
                if name not in ci.ftypes:
                    self.exc_attr(ci, name)
                    why = self.ann_problem(st.kids[1], False) if k == "annassign" and ci.mod != "" else ""
                    t = "" if why != "" else self.vtype(st.kids[1]) if k == "annassign" else self.guess(st.kids[-1], f)
                    if t.startswith("!"):
                        why = t[1:]  # (a call of a function Pystachy cannot compile: its error)
                    t = "" if t == "None" or why != "" else t  # (f() that returns None: a field has a value type)
                    if t == "" and why == "":
                        why = f"cannot infer the type of field '{name}'; annotate it (self.{name}: T = ...)"
                    if t == "" and ci.mod == "":
                        self.err(why)
                    if t == "":
                        # an imported module's class: an error only where the program uses it
                        ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
                        t = "int"
                    self.add_field(ci, name, t)
            for kid in st.kids:
                if kid.kind == "block":
                    self.scan_fields(ci, f, kid.kids)
                elif kid.kind == "except":
                    self.scan_fields(ci, f, kid.kids[1].kids)

    def guess(self, e: Node, f: FnInfo) -> str:
        k = e.kind
        if k == "int" or k == "float" or k == "str":
            return k
        if k == "True" or k == "False":
            return "bool"
        if k == "fstr":
            return "str"
        if k == "unary" and e.s != "not":
            t = self.guess(e.kids[0], f)
            return "int" if t == "bool" else t  # (-True is -1, as unary() computes it)
        if k == "name" and e.s in f.params:
            t = f.ptypes[f.params.index(e.s)]
            return t if t != "" or f.bad == "" else "!" + f.bad  # (a parameter whose annotation failed)
        if k == "call" and len(e.kids) == 2 and self.imported_ref(e.kids[0]) == "os.fspath" and unopt(self.guess(e.kids[1], f)) == "str":
            return "str"  # (a str path is its own file system path)
        if k == "call" and e.kids[0].kind == "name":
            c = e.kids[0].s
            if c in self.classes or c in self.unsupported:
                return c if c in self.classes else "!" + self.unsupported[c]
            if c in self.funcs:
                return self.funcs[c].ret if self.funcs[c].bad == "" else "!" + self.funcs[c].bad
            if c == "str" or c == "int" or c == "float" or c == "bool":
                return c
            if c == "len" or c == "ord":
                return "int"
            if c == "input" or c == "repr" or c == "chr" or c == "ascii":
                return "str"
            if c == "open":
                return "file"
        if k == "call" and e.kids[0].kind == "attr" and e.kids[0].kids[0].kind == "name" and e.kids[0].kids[0].s in self.classes:
            ms = self.classes[e.kids[0].kids[0].s].methods  # C.m(...): a static or class method
            return ms[e.kids[0].s].ret if e.kids[0].s in ms and ms[e.kids[0].s].deco != "" else ""
        me = f.params[0] if takes_self(f) else ""
        if k == "attr" and e.kids[0].kind == "name" and e.kids[0].s == me:
            return self.classes[f.cls].ftypes.get(e.s, "")
        if k == "call" and e.kids[0].kind == "attr" and e.kids[0].kids[0].kind == "name" and e.kids[0].kids[0].s == me:
            ms = self.classes[f.cls].methods
            m = e.kids[0].s
            return "" if m not in ms else ms[m].ret if ms[m].bad == "" else "!" + ms[m].bad
        if k == "cmp" or (k == "unary" and e.s == "not"):
            return "bool"
        if k == "ifexp":
            return self.guess(e.kids[1], f)
        if k == "list" and len(e.kids) > 0:
            t = self.guess(e.kids[0], f)
            return f"list[{t}]" if t != "" and not t.startswith("!") else t
        if k == "tuple" and 0 < len(e.kids) <= 9:
            ts = [self.guess(x, f) for x in e.kids if x.kind != "starred"]
            bad = [t for t in ts if t.startswith("!")]
            if len(bad) > 0:
                return bad[0]
            return f"tuple[{','.join(ts)}]" if "" not in ts and len(ts) == len(e.kids) else ""
        if k == "dict" and len(e.kids) > 0 and len(e.kids) % 2 == 0:
            kt = self.guess(e.kids[0], f)
            vt = self.guess(e.kids[1], f)
            if kt.startswith("!") or vt.startswith("!"):
                return kt if kt.startswith("!") else vt
            return f"dict[{kt},{vt}]" if kt != "" and vt != "" and key_problem(kt) == "" else ""
        if k == "call" and e.kids[0].kind == "name" and (e.kids[0].s == "list" or e.kids[0].s == "sorted") and len(e.kids) == 2 and not self.bound(e.kids[0].s):
            # list(range(n)), list(xs), sorted(xs): a list of the items
            arg = e.kids[1]
            if arg.kind == "call" and arg.kids[0].kind == "name" and arg.kids[0].s == "range" and not self.bound("range"):
                return "list[int]"
            t = self.guess(arg, f)
            return t if is_list(t) or t.startswith("!") else ""
        if k == "binop":
            a = self.guess(e.kids[0], f)
            b = self.guess(e.kids[1], f)
            if self.isnum(a) and self.isnum(b):
                if e.s == "/" or a == "float" or b == "float":
                    return "float"
                return "bool" if a == "bool" and b == "bool" and e.s in IOPS else "int"
            if a == b and (a == "str" or is_list(a)):
                return a
            if e.s == "*" and (is_list(a) or a == "str") and (b == "int" or b == "bool"):
                return a  # [n] * n
            if e.s == "*" and (is_list(b) or b == "str") and (a == "int" or a == "bool"):
                return b
        return ""

    def field(self, o: Val, name: str, store: bool = False) -> Val:
        if name == "__class__" and (o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != "")):
            self.err("e.__class__ of an exception is not supported; type(e).__name__ is")
        if o.t == "exc":
            # (isinstance() does not change the type of the name an except clause binds)
            fl = [c for c in self.classes.values() if c.exc != "" and name in c.ftypes]
            hint = f" (to read the fields of {short(fl[0].name)}, catch it by its class: except {short(fl[0].name)} as e)" if len(fl) > 0 else ""
            self.err(f"the attributes of an exception (e.{name}) are not supported; str(e) and repr(e) are{hint}")
        if o.t not in self.classes:
            t = unopt(o.t)
            base = "list" if is_list(t) else "dict" if is_dict(t) else t
            if base + "." + name in METHODS:
                self.err(f"{tname(t)}.{name} is a method: call it, {name}(...) (methods are not values)")
            self.err(f"type {typestr(o.t)} has no attribute '{name}'")
        ci = self.classes[o.t]
        if name not in ci.ftypes:
            if name in ci.methods:
                self.err(f"{o.t}.{name} is a method: call it, {name}(...) (methods are not values)")
            if ci.exc != "":
                sub = [c for c in self.classes.values() if c.name != o.t and name in c.ftypes and self.derives(c.name, o.t)]
                if len(sub) > 0:
                    self.err(f"'{short(o.t)}' object has no attribute '{name}' (it is a field of {short(sub[0].name)}, which derives from {short(o.t)}: isinstance() does not change the type of a value)")
                for b in EXCATTRS:
                    if name in EXCATTRS[b].split() and exc_derives(ci.exc, b):
                        self.err(f"'{short(o.t)}' object has no attribute '{name}': {b}'s attribute {name} is not supported (str(e) and repr(e) are)")
                for b in EXCINIT:
                    if name in EXCINIT[b].split() and exc_derives(ci.exc, b):
                        self.err(f"'{short(o.t)}' object has no attribute '{name}': {b}'s attribute {name} is not supported (a field of the class assigned in __init__, after super().__init__(...), is)")
                self.err(f"'{short(o.t)}' object has no attribute '{name}' (of an exception object, only the fields of its class are supported; str(e) and repr(e) are)")
            self.err(f"'{o.t}' object has no attribute '{name}'")
        extra = " and no __dict__ for setting new attributes" if store else ""
        self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{name}'{extra}")
        return Val(self.fgep(o, ci.fpos[name]), ci.ftypes[name])

    def fgep(self, o: Val, i: int) -> str:
        # the address of field or flag i of object o (IFn.fa holds it, for rawfx)
        r = self.ins(f"getelementptr %C.{o.t}, ptr {o.v}, i32 0, i32 {i}")
        self.fn.fa[r] = True
        return r

    def getfield(self, o: Val, p: Val, name: str) -> Val:
        # load a field (p = self.field(o, name)); a field __init__ may leave unassigned is checked
        ci = self.classes[o.t]
        if o.t + "." + name in self.cvars:
            # a class variable: the object's own value once it has assigned one, else the class's
            own = self.ins(f"load i1, ptr {self.fgep(o, ci.fflag[name])}")
            fv = Val(self.ins(f"load {lt(p.t)}, ptr {p.v}"), p.t)
            self.class_default(ci, name)
            r = self.select(own, fv, Val(self.ins(f"load {lt(p.t)}, ptr {ci.fglob[name]}"), p.t))
            if is_opt(p.t):
                self.wide[self.curfn.ll + r] = True  # (not narrowed, see coerce)
            return Val(r, p.t)
        if name in ci.fflag:
            f = self.fgep(o, ci.fflag[name])
            bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr {f}')}, true")
            subs = [x for x in self.classes.values() if x.base == o.t]
            if len(subs) > 0:
                # an exception object, of o.t or a class deriving from it: CPython names its class
                l1 = self.label()
                l2 = self.label()
                self.cbr(bad, l1, l2)
                self.place(l1)
                c = self.rt("pys_exc_cls", "ptr", [f"ptr {o.v}"])
                q = self.sconst("'")
                t = self.sconst("' object has no attribute '" + name + "'")
                m = self.rt("pys_str_add", "ptr", [f"ptr {q}", f"ptr {c}"])
                m = self.rt("pys_str_add", "ptr", [f"ptr {m}", f"ptr {t}"])
                self.raise_("AttributeError", m)
                self.place(l2)
            else:
                self.guard(bad, f"AttributeError: '{tname(o.t)}' object has no attribute '{name}'")
        r = self.ins(f"load {lt(p.t)}, ptr {p.v}")
        if is_opt(p.t):
            self.wide[self.curfn.ll + r] = True  # (not narrowed, see coerce)
        return Val(r, p.t)

    def setfield(self, o: Val, p: Val, name: str, v: Val) -> None:
        what = f"the value assigned to field '{name}' ({typestr(p.t)})" if is_opt(v.t) else ""
        self.emit(f"store {lt(p.t)} {self.coerce(v, p.t, what).v}, ptr {p.v}")
        ci = self.classes[o.t]
        if name in ci.fflag:
            self.emit(f"store i1 true, ptr {self.fgep(o, ci.fflag[name])}")

    # ---- variables
    def global_var(self, g: str, ty: str) -> None:
        # every module-level variable, visible or hidden, is defined here: the garbage
        # collector scans the pointer-typed ones, whose addresses @main hands to pys_init
        self.globs.append(f"{g} = internal global {ty} zeroinitializer")
        if ty == "ptr":
            self.gcroots.append(g)

    def is_global(self, name: str) -> bool:
        if name in self.ltype or name in self.compvars:
            return False
        return self.modlevel or name in self.gdecl or "$" in name

    def unbound_local(self, name: str) -> bool:
        # a local of the function that is not declared yet: one that the function assigns later
        # (which hides the module's variable, function, class or import of that name)
        return name in self.assigned and name not in self.gdecl and name not in self.ltype

    def no_type(self, name: str) -> None:
        # the error for the empty list or dict of variable name, still without a type where a use
        # needs it (an annotation of it belongs where the container was made, see origin)
        t = self.qtype(name)
        src = name
        while src in self.origin and name not in self.ltype:
            src = self.origin[src]
        self.err(f"cannot infer the type of '{short(name)}', an empty {'list' if is_list(t) else 'dict'} so far: annotate it{self.where_def(src)} ({short(src)}: {'list[T] = []' if is_list(t) else 'dict[K, V] = {}'})")

    def load_name(self, name: str) -> Val:
        if (name in self.nonevars or name in self.noneglobals) and name not in self.ltype:
            return Val("null", "None")
        if "?" in self.qtype(name) and not self.allowq and self.lookahead(name) == "":
            t = self.qtype(name)
            if self.unfilled(name) and self.dead and not aliases(self.curfn.node.kids[2], name):
                # only code these argument types leave out fills it, and nothing else gets it to
                # fill: it is always empty here
                self.refine(name, "list[int]" if is_list(t) else "dict[int,int]")
                self.guessed[self.curfn.ll] = f"'{name}' of {short(self.curfn.name)}() is always empty for these arguments, and taken as {typestr(self.ltype[name])}: annotate it ({name}: {'list[T] = []' if is_list(t) else 'dict[K, V] = {}'})"
            elif not self.globread(name) or self.copying or "?" in self.early(name):
                self.no_type(name)
        if name in self.ltype:
            t = self.ltype[name]
            if t == NONEVAR:
                t = self.none_read(name)
                if t == "None":
                    return Val("null", "None")
            r = self.ins(f"load {lt(t)}, ptr {self.lreg[name]}")
            if name == self.selfname and name not in self.compvars:
                self.nn[r] = True
            if name in self.narrowed and is_opt(t) and t != NONEVAR:
                return self.deref(Val(r, t))  # known not to be None here
            return Val(r, t)
        if self.unbound_local(name):
            self.err(f"local variable '{name}' is read before its first assignment; declare it first ({name}: T)")
        if name in self.gtypes:
            t = self.gtypes[name]
            r = self.ins(f"load {lt(t)}, ptr @g.{name}")
            if is_opt(t):
                self.wide[self.curfn.ll + r] = True  # (not narrowed, see coerce)
            return Val(r, t)
        if name == "__name__":
            return Val(self.sconst("__main__"), "str")
        if name in self.aliases:
            return self.modattr(self.aliases[name])
        if name in self.funcs:
            self.err(f"function '{name}' cannot be used as a value")
        if name in self.classes:
            self.err(f"class '{name}' cannot be used as a value (classes are not values: call it, or read an attribute, C.x)")
        if name in self.fglobals:
            self.err(f"name '{name}' is not defined yet here: a function assigns it, so declare it at module level{self.where_def(name)} first ({short(name)}: T)")
        if name in self.mvars and owner(name) != self.curfn.mod and owner(name) not in self.inited and self.comp[owner(name)] == self.comp[self.curfn.mod]:
            # (see ahead; this module imports that one, as it reads its global: that module imports
            # this one back if both are in one component of the import graph)
            self.err(f"'{short(name)}' of module {owner(name)} is read here while that module is still being imported (a circular import), when only its constants (NAME = literal) can be read: read it in a function that runs after the import")
        if name in self.mvars and owner(name) != self.curfn.mod and owner(name) not in self.inited:
            # no cycle: this module imports it later (in a function), so its code is compiled later
            self.err(f"the type of '{short(name)}' of module {owner(name)} is not known here, as this module's code is compiled before that module's code, which it imports later: import {owner(name)} at the top of {self.mfile[self.curfn.mod]}")
        if name in self.mvars:
            src = self.origin.get(name, name)
            self.err(f"the type of '{short(name)}' is not known yet here, before its module's code assigns it: declare it at module level{self.where_def(src)} first ({short(src)}: T)")
        if name in self.unsupported:
            self.err(self.unsupported[name])
        if name in PYBUILTINS:
            self.err(f"the builtin '{name}' cannot be used as a value (not supported)")
        if name in MODDUNDERS.split():
            self.err(f"'{name}' is not supported")  # (a module attribute that CPython defines)
        if name in self.typevars:
            self.err(f"TypeVar '{short(name)}' cannot be used as a value (only annotations may name it)")
        self.err(f"name '{short(name)}' is not defined")
        return Val("", "")

    def none_read(self, name: str) -> str:
        # a read of local name, which only None has been assigned so far: a binding of another value
        # in the function's source that can be typed here gives it its type, else only a comparison
        # with None may read it
        t = self.none_type(name)
        if t != "":
            self.ltype[name] = t
            return t
        body = self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids
        if only_none(body, name):
            return "None"  # (it is None wherever it is assigned)
        if not self.nonecmp:
            self.err(f"cannot infer the type of '{name}' from None here, before a value of another type is assigned to it; annotate it ({name}: T | None)")
        return NONEVAR

    def none_type(self, name: str) -> str:
        # the type of variable name, first assigned None: T | None for the first other value that
        # the code of its function (or module) assigns it, also by unpacking, that can be typed here
        # (as lookahead does); "" if there is none
        body = self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids
        found: list[Node] = []
        self.none_values(body, name, found)
        for e in found:
            if e.kind != "None" and not empty_display(e) and self.typed_now(e) and not self.calls_open(e, {}):
                # (typed as where it is assigned, under tests of the optional locals it reads)
                pre = self.narrowed
                self.narrowed = dict(pre)
                for nm in self.ltype:
                    self.narrowed[nm] = True
                t = self.dry(e)
                self.narrowed = pre
                if t != "None" and t != "" and "?" not in t and t != NONEVAR:
                    if self.optional(t) == "":
                        self.err(f"'{name}' is assigned None and {typestr(t)}, and None/Optional is only supported for {OPTTYPES}")
                    return self.optional(t)
        return ""

    def none_values(self, body: list[Node], name: str, out: list[Node]) -> None:
        # the values that statements in body (into blocks, in order) assign to variable name: of
        # a, b = e the item of e (an index node if e is not a display)
        for st in body:
            if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
                continue
            if st.kind == "assign":
                e = st.kids[-1]
                for t in st.kids[:-1]:
                    if t.kind == "name" and t.s == name:
                        out.append(e)
                    elif t.kind == "tuple" or t.kind == "list":
                        for i in range(len(t.kids)):
                            if t.kids[i].kind == "name" and t.kids[i].s == name:
                                disp = (e.kind == "tuple" or e.kind == "list") and len(e.kids) == len(t.kids)
                                out.append(e.kids[i] if disp else mk("index", "", e.line, [e, mk("int", str(i), e.line, [])]))
            for kid in st.kids:
                if kid.kind == "block":
                    self.none_values(kid.kids, name, out)
                elif kid.kind == "except":
                    self.none_values(kid.kids[1].kids, name, out)

    def read(self, n: Node) -> Val:
        # a variable read; if flow analysis found it may be unassigned, check at run time
        name = n.s
        self.gtype(name)
        if n.chk and name in self.ltype:
            if name in self.lflag and name not in self.compvars:
                bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr {self.lflag[name]}')}, true")
                self.guard(bad, f"UnboundLocalError: cannot access local variable '{name}' where it is not associated with a value")
        elif (n.chk or self.foreign(name)) and name in self.gflag and name in self.gtypes:
            bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{name}.def')}, true")
            self.guard(bad, self.unbound(name, self.copying))
        return self.load_name(name)

    def modchk(self, n: Node) -> None:
        # n reads module m's attribute through a name that an import in a try statement binds
        # (Node.mchk): if that import raised, m's code did not end (its done flag is clear, see
        # function), and CPython left the name unbound
        if n.mchk == "":
            return
        p = n.mchk.split(" ")
        un = f"UnboundLocalError: cannot access local variable '{p[1]}' where it is not associated with a value" if p[2] == "L" else f"NameError: name '{p[1]}' is not defined"
        self.guard(self.ins(f"xor i1 {self.ins(f'load i1, ptr @init.{p[0]}.done')}, true"), un)

    def foreign(self, name: str) -> bool:
        # another module's global that may be unbound when this code reads it
        return name in self.late and owner(name) != self.curfn.mod

    def unbound(self, name: str, imp: bool = False) -> str:
        # what CPython raises for reading name unbound (as M.x from another module, or imp: by
        # from M import x, naming the file of M, as found when compiling)
        if self.foreign(name) and imp:
            f = self.mfile[owner(name)]
            where = os.path.realpath(f) if f.endswith(".py") else "unknown location"
            return f"ImportError: cannot import name '{short(name)}' from '{owner(name)}' ({where})"
        if self.foreign(name):
            return f"AttributeError: module '{owner(name)}' has no attribute '{short(name)}'"
        return f"NameError: name '{short(name)}' is not defined"

    def qtype(self, name: str) -> str:
        # the type of variable name here, or ""
        if name in self.ltype:
            return self.ltype[name]
        if name not in self.compvars and (self.is_global(name) or name not in self.assigned):
            return self.gtypes.get(name, "")
        return ""

    def rtype(self, name: str) -> str:
        # the type of variable name read here (see gtype), or ""
        return self.gtype(name) if self.globread(name) else self.qtype(name)

    def globread(self, name: str) -> bool:
        # does reading name here read a module global
        return name not in self.ltype and name not in self.compvars and name not in self.nonevars and (self.is_global(name) or name not in self.assigned)

    def where_def(self, name: str) -> str:
        # " in FILE" for a global of another module than the code being compiled: where a fix-it goes
        return f" in {self.mfile[owner(name)]}" if "$" in name and owner(name) in self.mfile and owner(name) != self.curfn.mod else ""

    def gtype(self, name: str) -> str:
        # the type of module global name read here, also where the code that gives it its type
        # has not been compiled yet (see ahead and early), or ""
        if name not in self.gtypes and name in self.mvars and name not in self.noneglobals and not self.copying and self.globread(name) and self.ahead(name) == "":
            self.early(name)
        return self.gtypes.get(name, "")

    def ahead(self, name: str) -> str:
        # module global name, read by code compiled before its module's code assigns it (a template's
        # function called before that, a function compiled early): its first binding in that code
        # (in the branches that run, see live_blocks) gives it its type now, if it is an annotation,
        # or an assignment (also a, b = ...) whose value can be typed here (its variables have
        # types), or of an empty container that code fills (as lookahead finds it, also through
        # its twins); "" if not. Not for code of another module: that runs while the module is
        # still being imported (a circular import), and when the global is unbound then, CPython's
        # AttributeError says so and names the module's file
        if name in self.gtypes or name in self.busy or owner(name) not in self.inits or owner(name) != self.curfn.mod:
            return self.gtypes.get(name, "")
        self.busy[name] = True
        fr = self.modframe(owner(name), self.line)
        st = self.first_binding(self.inits[owner(name)].node.kids, name)
        if st is None:
            self.restore(fr)
            del self.busy[name]
            return ""
        self.line = st.line
        e = st.kids[-1]
        copying = self.copying
        self.copying = st.s == "from" and self.foreign(e.s)  # (see copying)
        if st.kind == "annassign" and st.kids[0].kind == "name":
            self.new_global(name, self.vtype(st.kids[1]))
        elif st.kind == "assign" and assigns(st, name) and (e.kind == "list" or e.kind == "dict") and len(e.kids) == 0:
            self.new_global(name, "list[?]" if e.kind == "list" else "dict[?,?]")
            self.lookahead(name, True)
        elif st.kind == "assign" and len(st.kids) == 2 and assigns(st, name) and e.kind == "name" and not self.copying and self.globread(e.s) and "?" in self.gtype(e.s):
            # X = Y of such a container (from m import Y): twins (see stmt), typed as above
            self.new_global(name, self.gtypes[e.s])
            self.twin(name, e.s)
            self.lookahead(name, True)
        elif st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "tuple":
            t = self.unpacked(st, name)
            if t != "" and t != "None" and "?" not in t and name not in self.gtypes:
                self.new_global(name, t)
        elif st.kind == "assign" and assigns(st, name) and self.typed_now(e) and not self.calls_open(e, {}):
            t = self.dry(e)
            # (typing e may have typed name: a function it compiled assigns it, and the module's
            # code checks the value's type where it stores it)
            if t != "" and t != "None" and "?" not in t and name not in self.gtypes:
                self.new_global(name, t)
        if self.copying and name not in self.gtypes:
            self.origin[name] = e.s  # (a declaration of it belongs in its module, see load_name)
        self.copying = copying
        self.restore(fr)
        del self.busy[name]
        return self.gtypes.get(name, "")

    def unpacked(self, st: Node, name: str) -> str:
        # the type that a, b = ... (assignment st) gives name, one of its targets, if its value can
        # be typed here (see typed_now) and calls no template being compiled (see calls_open); or ""
        t0 = st.kids[0]
        e = st.kids[1]
        i = 0
        while i < len(t0.kids) and not (t0.kids[i].kind == "name" and t0.kids[i].s == name):
            i += 1
        if i == len(t0.kids):
            return ""
        if (e.kind == "tuple" or e.kind == "list") and len(e.kids) == len(t0.kids):
            e = e.kids[i]  # (each item is assigned on its own, see stmt)
            return self.dry(e) if self.typed_now(e) and not self.calls_open(e, {}) else ""
        if not self.typed_now(e) or self.calls_open(e, {}):
            return ""
        t = self.dry(e)
        if is_tuple(t):
            return targs(t)[i] if len(targs(t)) == len(t0.kids) else ""
        return elem(t) if is_list(t) else t if t == "str" else ""

    def twin(self, x: str, y: str) -> None:
        # module globals x and y hold the same empty container without a type (x = y): one type,
        # which the first use of either gives (an annotation belongs where y got the container)
        # (and the twins of either: from m2 import Y, where m2 did from m1 import Y)
        a = self.twin_of.get(x, x)
        b = self.twin_of.get(y, y)
        if a != b:
            if len(self.twin_set.get(a, [a])) < len(self.twin_set.get(b, [b])):
                c = a
                a = b
                b = c
            if a not in self.twin_set:
                self.twin_set[a] = [a]
                self.twin_of[a] = a
            for nm in self.twin_set.pop(b, [b]):
                self.twin_of[nm] = a
                self.twin_set[a].append(nm)
            self.origin[x] = y

    def twins(self, x: str) -> list[str]:
        # the twins of global x
        return [nm for nm in self.twin_set.get(self.twin_of.get(x, ""), []) if nm != x]

    def calls_open(self, n: Node, seen: dict[str, bool]) -> bool:
        # does n call, also through the templates' functions it calls (which a call compiles), a
        # template's function being compiled whose return type is not known yet (as the read that
        # ahead types may be in it)
        if n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s in self.funcs and self.funcs[n.kids[0].s].generic and n.kids[0].s not in seen:
            f = self.funcs[n.kids[0].s]
            seen[n.kids[0].s] = True
            for g in f.insts.values():
                if g.ret == "" or "?" in g.ret:
                    return True  # (or whose return type is open, see retval)
            if self.calls_open(f.node.kids[2], seen):
                return True
        for k in n.kids:
            if self.calls_open(k, seen):
                return True
        return False

    def modframe(self, mod: str, line: int) -> Frame:
        # compile in the frame of module mod's top-level code from here (at line) to restore(the
        # frame returned)
        fr = self.save()
        self.modlevel = True
        self.lenient = False
        self.enter(self.inits[mod], [])
        self.line = line
        return fr

    def modtype(self, e: Node, mod: str) -> str:
        # the type of expression e of module mod's top-level code, compiled here into code that is
        # dropped; "" if a variable it reads has no type yet
        fr = self.modframe(mod, self.line)
        t = self.dry(e) if self.typed_now(e) else ""
        self.restore(fr)
        return t

    def early(self, name: str) -> str:
        # module global name, which has no type here or holds an empty container without one,
        # read before the function that shows its type is compiled: a function that assigns the
        # global or fills the container (or the twins of name, see twins) is compiled now
        names = [name] + self.twins(name)
        fs: list[FnInfo] = [f for f in self.funcs.values()]
        for ci in self.classes.values():
            if ci.bad == "":
                fs.extend(ci.methods.values())
        for f in fs:
            if name in self.gtypes and "?" not in self.gtypes[name]:
                break
            if f.generic or f.bad != "" or f.ll in self.compiled or not self.sets(f, names) or not self.decides(f, names) or self.unready(f.node.kids[2], f.mod, {}):
                continue
            self.making.append(f"compiling {f.name if f.cls == '' else f.cls + '.' + f.name}() for the type of '{name}' at {where(self.line)}")
            fr = self.save()
            self.modlevel = False
            self.lenient = False
            self.function(f, f.node.kids[2].kids)
            self.restore(fr)
            self.making.pop()
        return self.gtypes.get(name, "")

    def unready(self, n: Node, mod: str, seen: dict[str, bool]) -> bool:
        # does n, code of module mod, read a global without a type of another module whose code is
        # not compiled yet, also through the templates' functions it calls (which a call compiles):
        # compiled now (see early), it would seem to read it during a circular import
        if n.kind == "name" and n.s in self.mvars and n.s not in self.gtypes and n.s not in self.noneglobals and owner(n.s) != mod and owner(n.s) not in self.inited:
            return True
        if n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s in self.funcs and self.funcs[n.kids[0].s].generic and n.kids[0].s not in seen:
            f = self.funcs[n.kids[0].s]
            seen[n.kids[0].s] = True
            if self.unready(f.node.kids[2], f.mod, seen):
                return True
        for k in n.kids:
            if self.unready(k, mod, seen):
                return True
        return False

    def decides(self, f: FnInfo, names: list[str]) -> bool:
        # does the first fill of the containers names in function f (see fills) show what they
        # hold, so that compiling f now can give them a type: not d[k] = [] or d.setdefault(k, {}),
        # unless the type expected of the call types its empty default (return d.get(k, []))
        body = f.node.kids[2].kids
        fr = self.save()
        self.modlevel = False
        self.enter(f, body)
        found: list[Node] = []
        for nm in names:
            self.fills(body, nm, found)
        self.restore(fr)
        return len(found) == 0 or not empty_display(found[-1]) or typed_default(body, found[-1], is_list(f.ret) or is_dict(f.ret))

    def sets(self, f: FnInfo, names: list[str]) -> bool:
        # does function f assign one of the module globals names, or fill the container it holds
        body = f.node.kids[2].kids
        loc: dict[str, bool] = {}
        decl: dict[str, bool] = {}
        local_names(body, loc)
        globals_in(body, decl)
        for p in f.params:
            loc[p] = True
        for nm in names:
            if (nm not in loc or nm in decl) and shows_items(mk("block", "", 0, body), nm):
                return True
        return False

    def first_binding(self, body: list[Node], name: str) -> Node | None:
        # the first statement in body, in order and into the blocks that run (see live_blocks; not
        # into functions and classes), that binds name (for none_ends, not to None)
        for st in body:
            if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
                continue
            if stmt_binds(st, name) and not (self.whole < 0 and st.kind == "assign" and st.kids[-1].kind == "None"):
                return st
            for kid in self.live_blocks(st):
                r = self.first_binding(kid.kids, name)
                if r is not None:
                    return r
        return None

    def only_empties(self, body: list[Node], name: str) -> bool:
        # is every binding of name in body (into the blocks that run) an assignment of an empty [] or {}
        for st in body:
            if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
                continue
            v = st.kids[-1] if st.kind == "assign" else st
            empty = len(st.kids) == 2 and st.kids[0].kind == "name" and (v.kind == "list" or v.kind == "dict") and len(v.kids) == 0
            if stmt_binds(st, name) and not empty:
                return False
            for kid in self.live_blocks(st):
                if not self.only_empties(kid.kids, name):
                    return False
        return True

    def live_blocks(self, st: Node) -> list[Node]:
        # the blocks of statement st that a static test (see static) does not leave out: of an if
        # decided here the branch that runs, of a while loop whose test is false its else block
        # (and the bodies of a try statement's except clauses)
        s = -1 if st.kind != "if" and st.kind != "while" else self.static_now(st.kids[0]) if self.whole == 0 else self.static_whole(st.kids[0], st.line)
        bs: list[Node] = []
        for i in range(len(st.kids)):
            kid = st.kids[i]
            if kid.kind == "block" and not (st.kind == "if" and s >= 0 and i == (2 if s == 1 else 1)) and not (st.kind == "while" and s == 0 and kid.s != "else"):
                bs.append(kid)
            elif kid.kind == "except":
                bs.append(kid.kids[1])
        return bs

    def static_now(self, n: Node) -> int:
        # static(n), also in module code compiled before the code that types the globals n reads
        # (see ahead): they get their types first, as where the module's code compiles the test
        if self.modlevel:
            self.type_reads(n)
        return self.static(n)

    def static_whole(self, n: Node, line: int) -> int:
        # static_now(n) for the test of the if at line, in code that compiles later (see fills):
        # with the facts that hold there (see static_type)
        if self.modlevel:
            self.type_reads(n)
        here = self.line
        w = self.whole
        self.whole = line
        self.line = line
        self.unsure = False
        s = self.static(n)
        self.whole = w
        self.line = here
        return s

    def none_ends(self) -> None:
        # for each parameter whose argument is None, the line of the first statement, in the blocks
        # that may run, that binds it to something else than None (a large number if none does):
        # it is None before. Tests of them are decided by the lines found so far (at first none,
        # each one a line it is None up to at least), until they stay the same
        again = True
        while again:
            again = False
            for p in self.nonevars:
                self.whole = -1  # (live_blocks decides the tests as fills does)
                st = self.first_binding(self.curfn.node.kids[2].kids, p)
                self.whole = 0
                again = again or (st.line if st is not None else 1 << 40) != self.nonevars[p]
                self.nonevars[p] = st.line if st is not None else 1 << 40

    def type_reads(self, n: Node) -> None:
        if n.kind == "name":
            self.gtype(n.s)
        for k in n.kids:
            self.type_reads(k)

    def empty(self, kind: str, name: str) -> Val:
        # [] or {} assigned to a variable without a type: the first use that shows what it holds
        # gives the variable its type (fill, refine); until then only len() and truth tests read it
        i = self.hole(kind)
        if self.is_global(name):
            self.gkk[name] = self.gkk.get(name, "") + f" {i.k}"
        else:
            self.lkk[name] = self.lkk.get(name, "") + f" {i.k}"
        return Val(f"%t{i.r[0]}", i.t)

    def refine(self, name: str, t: str, glob: bool = False) -> None:
        # the variable holding an empty list or dict gets the type its first use shows (the module
        # global name if glob), and so do its twins
        if "?" in t or "None" in targs(t):
            self.err(f"cannot infer the type of '{name}' from this use; annotate it")
        if is_dict(t):
            t = f"dict[{none_items(targs(t)[0])},{targs(t)[1]}]"  # (d[k, None] = v)
        toks = ""
        if name in self.ltype and not glob:
            self.ltype[name] = t
            toks = self.lkk.pop(name, "")
            if "?" in self.ret and name in self.qret.get(self.curfn.ll, "").split():
                self.adopt(t)  # the function returned it: so it returns t
        else:
            for nm in [name] + self.twins(name):
                if nm == name or "?" in self.gtypes[nm]:
                    self.gtypes[nm] = t
                    toks += " " + self.gkk.pop(nm, "")
        if is_dict(t) and key_problem(targs(t)[0]) != "":
            self.err(key_problem(targs(t)[0]))
        for h in toks.split():
            self.holes[int(h)] = t
            if is_dict(t):
                self.key_kind(targs(t)[0])  # (a tuple key's descriptor, a string constant from here on, which lowering prints)

    def lookahead(self, name: str, ahead: bool = False) -> str:
        # an empty list or dict read before the code that fills it: the first use in this
        # function's source that shows its items (an append, d[k] = v, ...; of name or of a twin
        # of the global name) decides its type now, if the item expression reads only variables
        # whose types are already known here (for ahead, whose read may be in a template's
        # function being compiled, and calls none, see calls_open); "" if there is no such use
        body = self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids
        names = [name]
        if self.globread(name):
            for tw in self.twins(name):
                if self.globread(tw):
                    names.append(tw)
        found: list[Node] = []
        for nm in names:
            first: list[Node] = []
            self.live = True  # (a fill in a loop over the empty tuple only if no code that runs fills it)
            self.dead = False
            self.fills(body, nm, first)
            self.live = False
            if len(first) == 0 and self.dead:
                self.fills(body, nm, first)
            if len(first) > 0 and (len(found) == 0 or first[0].line < found[0].line):
                found = first
        if len(found) == 0:
            return ""
        t = self.qtype(name)
        e = found[-1]
        if empty_display(e):
            return ""  # (d[k] = [] shows nothing of what d holds)
        for x in found:
            if not self.typed_now(x) or (ahead and self.calls_open(x, {})):
                return ""
        if found[0].kind == "omit" and not is_list(t):
            return ""  # (d += ... or d.extend(...) on a dict: an error where it is compiled)
        it = self.dry(e)
        if found[0].kind == "omit" and is_list(t):
            if not is_list(it):
                return ""
            r = it
        elif is_list(t):
            r = f"list[{it}]"
        else:
            r = f"dict[{self.dry(found[0])},{it}]"
        if "?" in r or "None" in targs(r):
            return ""
        here = self.line
        self.line = e.line  # (a key type a dict cannot have is the fill's error)
        self.refine(name, r)
        self.line = here
        return r

    def unfilled(self, name: str) -> bool:
        # is name a local empty list or dict without a type, which no use in its function's source
        # types here (lookahead) and nothing in the function fills or rebinds, so that it is empty
        # wherever it is read? Fills in code the argument types leave out (a loop over the empty
        # tuple, a branch a static test removes) do not count; self.dead tells whether there are any
        if "?" not in self.ltype.get(name, "") or name in self.compvars or self.curfn.node.kind != "def" or self.lookahead(name) != "":
            return False
        found: list[Node] = []
        self.dead = False
        self.live = True
        self.fills(self.curfn.node.kids[2].kids, name, found)
        self.live = False
        return len(found) == 0 and self.only_empties(self.curfn.node.kids[2].kids, name)

    def retval(self, e: Node, want: str) -> Val:
        # the value of return e, where the function returns want ("" while a template's function
        # infers it). A template's function returns an empty container that nothing fills (see
        # unfilled) as it is, and each call gives it the type its context expects (typed_empty),
        # unless a use further on (in a loop, a call or another return) gives it a type (adopt)
        q = self.qret.get(self.curfn.ll, "")
        known = e.kind == "name" and e.s in q.split() and "?" in self.ltype.get(e.s, "")  # (and still so)
        if e.kind == "name" and (want == "" or "?" in want) and (known or self.unfilled(e.s)):
            self.qret[self.curfn.ll] = q if known else q + " " + e.s
            self.allowq = True
            v = self.read(e)
            self.allowq = False
            return v
        return self.expr(e, want)

    def adopt(self, t: str) -> None:
        # the template's function being compiled, which returned an empty container without a
        # type (see retval), returns t: the containers it returned have that type too
        if self.curfn.ll in self.qused:
            self.err(f"cannot infer what {short(self.curfn.name)}() returns: it calls itself before a use shows what the {tname(t)} it returns holds; annotate its return type")
        self.ret = t
        self.curfn.ret = t
        for nm in self.qret[self.curfn.ll].split():
            if "?" in self.ltype[nm]:
                self.refine(nm, t)

    def typed_empty(self, v: Val, want: str, f: FnInfo) -> Val:
        # the empty list or dict a template's function f returns (see retval): the type the call's
        # context expects, else list[int] or dict[int, int] (as sum() of an empty list is the int 0),
        # which a type error further on in this function then explains (guessed). A new dict is made
        # by each call, so it gets the key kind of its type here (a dict's second word)
        t = want if same_kind(want, v.t) and "?" not in want else "list[int]" if is_list(v.t) else "dict[int,int]"
        if t != want:
            self.guessed[self.curfn.ll] = f"{short(f.name)}() at line {self.line} returns an empty {tname(t)} taken as {typestr(t)}: give it a type first, as in v: {'list[T]' if is_list(t) else 'dict[K, V]'} = {short(f.name)}()"
        if is_dict(t):
            self.emit(f"store i64 {self.key_kind(targs(t)[0])}, ptr {self.ins(f'getelementptr i64, ptr {v.v}, i64 1')}")
        return Val(v.v, t)

    def fills(self, body: list[Node], name: str, found: list[Node]) -> bool:
        # the first statement in body (searched in order, into blocks) that fills variable name:
        # found gets [key or omit, item]. True if body ends in a return, raise, break or continue
        # (also in the branch of an if that the types decide), after which nothing in it runs
        for st in body:
            if len(found) > 0:
                return False
            if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
                continue
            k = st.kind
            s = self.static_whole(st.kids[0], st.line) if k == "if" or k == "while" else -1
            if k == "return" or k == "raise" or k == "break" or k == "continue":
                self.fill_calls(st, name, found)
                return True
            if (k == "assign" or k == "augassign") and st.kids[0].kind == "index" and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == name and k == "assign":
                found.append(st.kids[0].kids[1])
                found.append(st.kids[-1])
            elif k == "assign" and len(st.kids) == 2 and st.kids[0].kind == "index" and empty_default(st.kids[0].kids[0], name, "dict"):
                # name.setdefault(k, {})[k2] = v: the item is {k2: v} (see default_want)
                found.append(st.kids[0].kids[0].kids[1])
                found.append(mk("dict", "", st.line, [st.kids[0].kids[1], st.kids[1]]))
            elif k == "augassign" and st.kids[0].kind == "name" and st.kids[0].s == name and st.s == "+":
                found.append(mk("omit", "", st.line, []))
                found.append(st.kids[1])
            elif k == "if" and s >= 0:
                # a test that the types decide there: only the branch that runs
                self.dead = self.dead or shows_items(st.kids[2 if s == 1 else 1], name)
                if self.fills(st.kids[1 if s == 1 else 2].kids, name, found):
                    return True
            elif (k == "if" or k == "while") and self.unsure and shows_items(st, name):
                # a test that types not known yet may decide: which branch runs is not known
                found.append(mk("lambda", "", st.line, []))  # (which no look-ahead compiles)
            elif (k == "for" and self.live and st.kids[1].kind == "name" and self.qtype(st.kids[1].s) == "tuple[]") or (k == "while" and s == 0):
                # a loop over the empty tuple (*args without extra arguments), or whose test the
                # types make false: only its else block runs
                self.dead = self.dead or shows_items(st.kids[2 if k == "for" else 1], name)
                if st.kids[-1].s == "else":
                    self.fills(st.kids[-1].kids, name, found)
            else:
                self.fill_calls(st, name, found)
                for kid in st.kids:
                    if kid.kind == "block":
                        self.fills(kid.kids, name, found)
                    elif kid.kind == "except":
                        self.fills(kid.kids[1].kids, name, found)
        return False

    def fill_calls(self, n: Node, name: str, found: list[Node]) -> None:
        # name.append(v), insert(i, v), extend(xs), setdefault(k, v), get(k, v) anywhere in n
        if len(found) > 0 or n.kind == "block" or n.kind == "listcomp":
            return  # (a comprehension's names are its own)
        if n.kind == "call" and n.kids[0].kind == "attr" and len(n.kids) == (3 if n.kids[0].s == "insert" else 2) and (n.kids[0].s == "append" or n.kids[0].s == "insert") and n.kids[-1].kind != "kw" and empty_default(n.kids[0].kids[0], name, "list"):
            # name.setdefault(k, []).append(v): the item is [v] (see default_want)
            found.append(n.kids[0].kids[0].kids[1])
            found.append(mk("list", "", n.line, [n.kids[-1]]))
            return
        if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == name:
            m = n.kids[0].s
            a = n.kids[1:]
            if (m == "append" and len(a) == 1) or (m == "insert" and len(a) == 2):
                found.append(mk("int", "0", n.line, []))
                found.append(a[-1])
            elif m == "extend" and len(a) == 1:
                found.append(mk("omit", "", n.line, []))
                found.append(a[0])
            elif (m == "setdefault" or m == "get") and len(a) == 2:
                found.append(a[0])
                found.append(a[1])
            if len(found) > 0 and found[-1].kind == "kw":
                found.pop()
                found.pop()
            return
        s = self.static_whole(n.kids[0], n.line) if n.kind == "ifexp" or n.kind == "boolop" else -1
        if s < 0 and (n.kind == "ifexp" or n.kind == "boolop") and self.unsure and shows_items(n, name):
            found.append(mk("lambda", "", n.line, []))  # (as for an if: see fills)
        for i in range(len(n.kids)):
            # (not the operand of a conditional expression, and or or that the types leave out)
            if s < 0 or not ((n.kind == "ifexp" and i == (2 if s == 1 else 1)) or (n.kind == "boolop" and i == 1 and (s == 1) == (n.s == "or"))):
                self.fill_calls(n.kids[i], name, found)

    def typed_now(self, e: Node, own: str = "") -> bool:
        # can e be compiled here: every variable it reads has its type already (but own, the
        # variables of the comprehensions around e, space-separated)
        if e.kind == "name":
            if e.s in self.funcs or e.s in self.classes or e.s in self.aliases or e.s in own.split():
                return True
            t = self.rtype(e.s)
            if t != "":
                return "?" not in t and t != NONEVAR
            return not (e.s in self.assigned or e.s in self.mvars or e.s in self.nonevars)
        if e.kind == "listcomp":
            # [x for t in it if c]: x and c read the variables in t too, which the items of it type
            names: list[str] = []
            names_in(e.kids[1], names)
            inner = own + " " + " ".join(names)
            for i in range(len(e.kids)):
                if i != 1 and not self.typed_now(e.kids[i], own if i == 2 else inner):
                    return False
            return True
        if e.kind == "lambda" or e.kind in UNSUPPORTED:
            return False
        for k in e.kids:
            if not self.typed_now(k, own):
                return False
        return True

    def dry(self, e: Node) -> str:
        # the type of e, compiled into blocks that are dropped (an error after it is still the read's)
        blk = self.blk
        blocks = self.fn.blocks
        loops = self.fn.loops
        cur = self.cur
        term = self.term
        line = self.line
        self.blk = Blk("")
        self.fn.blocks = []
        self.fn.loops = []
        t = self.expr(e, "").t
        self.blk = blk
        self.fn.blocks = blocks
        self.fn.loops = loops
        self.cur = cur
        self.term = term
        self.line = line
        return t

    def fill(self, n: Node, m: str, args: list[Node], want: str = "") -> Val:
        # name.append(v), insert(i, v) or extend(xs) on a list, and name.setdefault(k, v) or
        # name.get(k, default) on a dict (where want, the type expected of the call, types an
        # empty default), whose variable has no type yet: the items decide it
        name = n.s
        self.allowq = True
        o = self.read(n)
        self.allowq = False
        for a in args:
            if a.kind == "kw":
                self.err(f"keyword arguments to {'list' if is_list(o.t) else 'dict'}.{m}() are not supported; pass them by position")
        if is_list(o.t) and (m == "append" or m == "extend" or m == "insert") and len(args) == (2 if m == "insert" else 1):
            if empty_display(args[-1]):
                self.no_type(name)  # (xs.append([]) shows nothing of what xs holds)
            i = self.ival(args[0]) if m == "insert" else Val("0", "int")
            if m == "extend" and args[0].kind == "listcomp" and args[0].s == "gen":
                # (item by item, as bmethod's)
                self.refine(name, self.listcomp(args[0], "", "", o.v).t)
                return Val("null", "None")
            v = self.as_list(self.consume(args[-1], ""), "extend") if m == "extend" else self.expr(args[-1], "")
            if m == "extend" and not is_list(v.t):
                self.err(f"cannot extend a list with {v.t}")
            self.refine(name, v.t if m == "extend" else f"list[{v.t}]")
            if m == "append":
                self.rt("pys_list_append", "void", [f"ptr {o.v}", "i64 " + self.to_slot(v)])
            elif m == "insert":
                self.rt("pys_list_insert", "void", [f"ptr {o.v}", f"i64 {i.v}", "i64 " + self.to_slot(v)])
            else:
                self.rt("pys_list_extend", "void", [f"ptr {o.v}", f"ptr {v.v}"])
            return Val("null", "None")
        if is_dict(o.t) and (m == "setdefault" or m == "get") and len(args) == 2:
            if empty_display(args[1]) and (want == "" or "?" in want):
                self.no_type(name)
            k = self.expr(args[0], "")
            v = self.expr(args[1], want if "?" not in want else "")
            self.refine(name, f"dict[{k.t},{v.t}]")
            return self.from_slot(self.rt(f"pys_dict_{m}", "i64", [f"ptr {o.v}", "i64 " + self.to_slot(k), "i64 " + self.to_slot(v)]), v.t)
        # any other method: the type a later use shows (or an error), then the method as usual
        return self.method(self.load_name(name), m, args)

    def default_want(self, r: Node, m: str, args: list[Node], vt: str) -> str:
        # d.setdefault(k, []).append(v) (or insert), or d.setdefault(k, {})[k2] = v (m "[]", args
        # [k2], vt the type of v), where d has no type yet: the type of the value, which then
        # types the empty default (see fill); else ""
        if r.kind != "call" or len(r.kids) != 3 or r.kids[0].kind != "attr" or r.kids[0].s != "setdefault" or r.kids[0].kids[0].kind != "name":
            return ""
        d = r.kids[2]
        if "?" not in self.rtype(r.kids[0].kids[0].s) or (d.kind != "list" and d.kind != "dict") or len(d.kids) > 0:
            return ""
        if m == "[]" and d.kind == "dict":
            return f"dict[{self.dry(args[0])},{vt}]"
        if d.kind == "list" and ((m == "append" and len(args) == 1) or (m == "insert" and len(args) == 2)) and args[-1].kind != "kw":
            return f"list[{self.dry(args[-1])}]"
        return ""

    def new_global(self, name: str, t: str) -> None:
        self.gtypes[name] = t
        self.global_var(f"@g.{name}", lt(t))
        if name in self.gflag:
            self.global_var(f"@g.{name}.def", "i1")

    def declare(self, name: str, t: str) -> None:
        if self.is_global(name):
            if name not in self.gtypes:
                self.new_global(name, t)
            old = self.gtypes[name]
        elif name in self.ltype:
            old = self.ltype[name]
        else:
            self.alloca(t, name)
            old = t
        if old != t:
            self.err(f"'{name}' was declared as {old}, not {t}")

    def store_name(self, name: str, v: Val) -> None:
        if name in self.noneglobals and name not in self.ltype:
            if v.t != "None":
                self.err(f"'{name}' is None in its module's code: giving it a {v.t} elsewhere (a function or another module) is not supported")
            return
        if self.is_global(name):
            if name not in self.gtypes:
                t0 = self.none_type(name) if v.t == "None" and self.modlevel else ""
                if v.t == "None" and t0 == "":
                    # (module code's other values for it are typed here, as far as they can be)
                    self.err(f"cannot infer the type of '{name}' from None; annotate it ({name}: T | None = None)")
                if v.t == "":
                    self.err(f"cannot infer the type of '{name}'; add a type annotation")
                self.declare(name, t0 if t0 != "" else v.t)
            t = self.gtypes[name]
            if "?" in t and same_kind(t, v.t) and "?" not in v.t:
                self.refine(name, v.t)
                t = v.t
            self.emit(f"store {lt(t)} {self.coerce(v, t, self.assigned_to(v, t, name)).v}, ptr @g.{name}")
            if name in self.gflag:
                self.emit(f"store i1 true, ptr @g.{name}.def")
        else:
            if name in self.nonevars and name not in self.ltype and name not in self.compvars:
                # a parameter whose argument is None: assigning None keeps it so; any other value
                # gives it that type from here on, which only code outside branches and loops can do
                if v.t == "None":
                    return
                if self.branch > 0:
                    self.err(f"'{name}' is None here, and giving it a {v.t if '?' not in v.t else v.t[: v.t.find('[')]} inside an if branch or a loop is not supported")
                self.nonevars[name] = self.line
            if name not in self.ltype and v.t == "None":
                # first None: T | None, typed by the first store of another value, or by a read
                # that needs the type before it (see none_read)
                self.alloca(NONEVAR, name)
            elif name not in self.ltype:
                self.alloca(v.t, name)
            t = self.ltype[name]
            if t == NONEVAR and v.t != "None":
                if self.optional(v.t) == "":
                    self.err(f"'{name}' is assigned None and {typestr(v.t)}, and None/Optional is only supported for {OPTTYPES}")
                t = self.optional(v.t)
                self.ltype[name] = t
            if "?" in t and same_kind(t, v.t) and "?" not in v.t:
                self.refine(name, v.t)
                t = v.t
            self.emit(f"store {lt(t)} {self.coerce(v, t, self.assigned_to(v, t, name)).v}, ptr {self.lreg[name]}")
            if name in self.lflag and name not in self.compvars:
                self.emit(f"store i1 true, ptr {self.lflag[name]}")
            if is_opt(t) and (is_opt(v.t) or v.t == "None"):
                self.narrowed.pop(name, False)
            elif is_opt(t):
                self.narrowed[name] = True  # (it holds a value)

    def assigned_to(self, v: Val, t: str, name: str) -> str:
        # what names value v assigned to variable name of type t, for coerce's error
        return f"the value assigned to '{short(name)}' ({typestr(t)})" if is_opt(v.t) else ""

    def target_type(self, n: Node, base: bool = False) -> str:
        # expected type of an assignment target (types empty [] / {} literals): a name, or a
        # chain of attributes and subscripts on one (g.groups["a"], d["x"]["y"]), whose base
        # name is only read, so in a function it can be a module-level variable
        if n.kind == "name":
            if base and n.s not in self.ltype and (n.s not in self.assigned or n.s in self.gdecl):
                return self.gtypes.get(n.s, "")
            return self.ltype.get(n.s, self.gtypes.get(n.s, "") if self.is_global(n.s) else "")
        if n.kind == "slice":
            self.err("assignment to a slice is not supported")
        if n.kind == "attr" or n.kind == "index":
            t = self.target_type(n.kids[0], True)
            if n.kind == "attr" and t in self.classes:
                return self.classes[t].ftypes.get(n.s, "")
            if n.kind == "index" and is_list(t):
                return elem(t)
            if n.kind == "index" and is_dict(t):
                return targs(t)[1]
            if n.kind == "index" and t in self.classes and "__setitem__" in self.classes[t].methods and len(self.classes[t].methods["__setitem__"].ptypes) > 2:
                return self.classes[t].methods["__setitem__"].ptypes[2]
        return ""

    def assign(self, t: Node, v: Val) -> None:
        k = t.kind
        if k == "badattr":
            self.err(t.s)
        if k in UNSUPPORTED:
            self.err(UNSUPPORTED[k])
        if k == "tuple" and len([x for x in t.kids if x.kind == "starred"]) > 0:
            self.err(UNSUPPORTED["starred"])  # (before the number of targets is checked)
        if k == "name":
            self.store_name(t.s, v)
        elif k == "attr" and self.dotted(t) != "":
            self.err(f"assigning to {self.dotted(t)} is not supported; change its value in place")
        elif k == "attr" and t.kids[0].kind == "name" and t.kids[0].s in self.classes and t.kids[0].s not in self.ltype:
            self.class_store(self.cvar(t.kids[0], t.s), t.s, v)
        elif k == "attr":
            o = self.expr(t.kids[0], "")
            p = self.field(o, t.s, True)
            self.frozen(o.t, t.s)
            self.setfield(o, p, t.s, v)
        elif k == "index" and t.kids[0].kind == "name" and "?" in self.rtype(t.kids[0].s):
            # d[k] = v or xs[i] = v on an empty dict or list without a type: k and v decide it
            self.allowq = True
            o = self.read(t.kids[0])
            self.allowq = False
            if is_dict(o.t):
                kval = self.expr(t.kids[1], "")
                self.refine(t.kids[0].s, f"dict[{kval.t},{v.t}]")
                self.rt("pys_dict_set", "void", [f"ptr {o.v}", "i64 " + self.to_slot(kval), "i64 " + self.to_slot(v)])
            else:
                ix = self.ival(t.kids[1])
                self.refine(t.kids[0].s, f"list[{v.t}]")
                self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {ix.v}", "i64 " + self.to_slot(v)])
        elif k == "index":
            o = self.expr(t.kids[0], self.default_want(t.kids[0], "[]", [t.kids[1]], v.t))
            nosub = "TypeError: 'NoneType' object does not support item assignment"
            if is_list(unopt(o.t)):
                ix = self.ival(t.kids[1])
                o = self.unwrap(o, nosub)
                s = self.to_slot(self.coerce(v, elem(o.t)))
                self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {ix.v}", f"i64 {s}"])
            elif is_dict(unopt(o.t)):
                kv = targs(unopt(o.t))
                key = self.to_slot(self.store_key(self.expr(t.kids[1], kv[0]), kv[0]))
                o = self.unwrap(o, nosub)
                self.rt("pys_dict_set", "void", [f"ptr {o.v}", f"i64 {key}", "i64 " + self.to_slot(self.coerce(v, kv[1]))])
            elif o.t in self.classes:
                # o[k] = v: o.__setitem__(k, v), once v, o and k are evaluated
                ik = self.expr(t.kids[1], self.argtype(o.t, "__setitem__", 1, f"'{tname(o.t)}' object does not support item assignment"))
                self.notnone(o, nosub)
                self.protocol(o, "__setitem__", [ik, v])
            else:
                self.err(f"'{o.t}' does not support item assignment")
        elif k == "tuple" and is_opt(v.t):
            self.assign(t, self.unwrap(v, "TypeError: cannot unpack non-iterable NoneType object"))
        elif k == "tuple" and (is_list(v.t) or v.t == "str"):
            # a, b = xs: the length is checked when it runs, as CPython does. CPython takes every
            # item before it stores the first, so where a store may change the list (xs[1], xs[0] =
            # xs, or a __setitem__ that empties it), the items are all read first
            self.rt("pys_unpack_check", "void", [f"i64 {self.ins(f'load i64, ptr {v.v}')}", f"i64 {len(t.kids)}"])
            first = v.t != "str" and not name_targets(t)
            items: list[Val] = []
            for i in range(len(t.kids)):
                if v.t == "str":
                    self.assign(t.kids[i], Val(self.rt("pys_str_get", "ptr", [f"ptr {v.v}", f"i64 {i}"]), "str"))
                elif first:
                    items.append(self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {v.v}", f"i64 {i}"]), elem(v.t)))
                else:
                    self.assign(t.kids[i], self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {v.v}", f"i64 {i}"]), elem(v.t)))
            for i in range(len(items)):
                self.assign(t.kids[i], items[i])
        elif k == "tuple" and v.t in self.nts:
            # a, b = p: a NamedTuple's fields in order
            fs = self.classes[v.t].fields
            if len(fs) != len(t.kids):
                self.err(f"cannot unpack {short(v.t)} ({len(fs)} fields) into {len(t.kids)} targets")
            self.notnone(v, "TypeError: cannot unpack non-iterable NoneType object")
            for i in range(len(fs)):
                self.assign(t.kids[i], self.getfield(v, self.field(v, fs[i]), fs[i]))
        elif k == "tuple" and v.t in self.classes:
            # a, b = o: what o's __iter__ steps through
            self.assign(t, self.obj_iter(v, "TypeError: cannot unpack non-iterable NoneType object", f"cannot unpack non-iterable {tname(v.t)} object"))
        elif k == "tuple":
            if not is_tuple(v.t) or len(targs(v.t)) != len(t.kids):
                self.err(f"cannot unpack {v.t} into {len(t.kids)} targets")
            for i in range(len(t.kids)):
                self.assign(t.kids[i], self.tget(v, i))
        else:
            self.err("cannot assign to this expression")

    # ---- functions and the module
    def enter(self, f: FnInfo, body: list[Node]) -> None:
        # the code generator's state at the start of function f, whose statements are body
        self.fn = IFn(f)
        self.blk = self.fn.blocks[0]
        self.ltype = {}
        self.lreg = {}
        self.gdecl = {}
        self.assigned = {}
        self.compvars = {}
        self.loops = []
        self.exits = []
        self.wdepth = []
        self.handler = ""
        self.excs = []
        self.shadows = []
        self.n = 0
        self.cur = "entry"
        self.term = False
        self.ret = f.ret
        self.retann = f.node.kind == "def" and f.node.kids[1].kind != "noann"
        self.nn = {}
        self.selfname = ""
        self.uflags = f.uflags
        self.lflag = {}
        self.lcs = []
        self.lct = []
        self.nonevars = {}
        self.narrowed = {}
        self.lkk = {}
        self.branch = 0
        self.curfn = f
        self.line = f.node.line
        if not self.modlevel:
            local_names(body, self.assigned)
            globals_in(body, self.gdecl)  # (global holds for the whole function, also from a dead branch)

    def function(self, f: FnInfo, body: list[Node]) -> None:
        if f.cls != "" and self.classes[f.cls].bad != "":
            self.err(self.classes[f.cls].bad)
        if f.bad != "" and not f.generic:
            self.err(f.bad)
        self.compiled[f.ll] = True
        self.building[f.ll] = True
        self.enter(f, body)
        if takes_self(f):
            # callers check the receiver, so self is never None inside a method
            self.nn["%a0"] = True
            if f.params[0] not in self.assigned:
                self.selfname = f.params[0]
        for i in range(len(f.params)):
            t = f.ptypes[i]
            if t == "None":
                # an argument that is None: the parameter is not passed, and reads of it are None
                self.nonevars[f.params[i]] = 0
                continue
            self.fn.ps.append(i)
            self.emit(f"store {lt(t)} %a{i}, ptr {self.alloca(t, f.params[i])}")
            if f.params[i] in self.lflag:
                self.emit(f"store i1 true, ptr {self.lflag[f.params[i]]}")  # (a parameter that del unbinds)
        self.none_ends()
        if f.name == "__init__" and f.cls != "" and not (self.is_dc(f.cls) and f.node.kids[0].kind == "noann") and self.classes[f.cls].exc == "":
            # class-body defaults (a synthesized dataclass __init__ assigns every field itself; an
            # exception class's constructor assigns them, see exc_object)
            ci = self.classes[f.cls]
            me = Val("%a0", f.cls)
            for fl in ci.fields:
                if fl in ci.fdefault and f.cls + "." + fl not in self.cvars:  # (a class variable is read from the class)
                    t = ci.ftypes[fl]
                    if not is_const(ci.fdefault[fl]):
                        self.class_default(ci, fl)  # (compiled before the class statement runs)
                    if fl in ci.fglob:
                        v = Val(self.ins(f"load {lt(t)}, ptr {ci.fglob[fl]}"), t)
                    else:
                        v = self.coerce(self.expr(ci.fdefault[fl], t), t)
                    self.setfield(me, self.field(me, fl), fl, v)
        if f.ll.startswith("@init."):
            # a module's code runs once, when the first import of it runs
            done = f.ll + ".done"
            self.global_var(done, "i1")
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.ins(f"load i1, ptr {done}"), l1, l2)
            self.place(l1)
            self.ret_(Val("null", "None"))
            self.place(l2)
            self.emit(f"store i1 true, ptr {done}")
        hm = ""
        mark = Val("", "")
        slot = ""
        if f.ll.startswith("@init.") and self.eh:
            # an exception that leaves a module's code leaves the module not imported, as CPython
            # removes it from sys.modules: a landing block around the code clears its done flag
            # and throws again, so that a later import runs the code again
            mark = Val(self.rt("pys_try_mark", "i64", []), "int")
            slot = self.alloca("exc", "")
            hm = self.label()
            tr = Try(self.label())
            tr.landing = hm
            self.fn.tries.append(tr)
            self.handler = hm
            self.place(tr.body)
        self.stmts(body)
        if f.ret == "":
            f.ret = "None"  # a template's function without a return statement that has a value
            f.noret = f.infer and self.term
            for b in self.fn.blocks:
                for x in b.code:
                    f.noret = f.noret and x.op != "ret" and x.op != "ret.none"
        if f.infer:
            # its returns of None, before it was known what it returns: None for an object, and
            # str, list, dict or tuple T make it return T | None (ret.none is lowered from f.ret)
            for b in self.fn.blocks:
                for x in b.code:
                    if x.op == "ret.none":
                        if f.ret != "None" and self.optional(f.ret) == "":
                            self.err(self.nonemix(f, f.ret))
                        if f.ret != self.optional(f.ret) and f.ret != "None":
                            self.reopt(self.optional(f.ret))
        if hm != "":
            if not self.term:
                self.ret_(Val("null", "None"))
            self.handler = ""
            e = self.landing(hm, slot, mark)
            self.emit(f"store i1 false, ptr {f.ll}.done")
            self.throw(e)
        if not self.term:
            if f.ret == "None" or (f.infer and f.ret in self.classes) or is_opt(f.ret):
                # (a template's function that ends without a return, or one returning T | None: None)
                self.ret_(Val("null", f.ret))
                if len(self.fn.cold) > 0:
                    # the jump to the first cold block that follows is a block of its own, which
                    # LLVM starts after a terminator, without a label
                    self.blk = Blk("")
                    self.fn.blocks.append(self.blk)
                    self.term = False
            else:
                self.raise_("RuntimeError", self.sconst(f"{short(f.name)}() ended without returning a value"))
        for key in self.fn.cold:
            self.place(self.fn.cold[key])
            msg = key
            if key in self.fn.coldh:
                self.blk.handler = self.fn.coldh[key]
                msg = key[len(self.fn.coldh[key]) + 1 :]
            i = msg.find(": ")
            self.raise_(msg[:i], self.sconst(msg[i + 2 :]))
        del self.building[f.ll]
        self.fn.n = self.n
        self.fns.append(self.fn)

    # ---- lowering: an IFn as LLVM text
    def lower(self, fn: IFn) -> None:
        o = self.out
        f = fn.f
        # a method's receiver is never None (callers check it)
        ps = [f"{lt(f.ptypes[j])}{' nonnull' if j == 0 and takes_self(f) else ''} %a{j}" for j in fn.ps]
        o.append(f"define internal {lt(f.ret)} {f.ll}({', '.join(ps)}){' personality ptr @pys_personality' if fn.pads else ''} {{")
        o.append("entry:")
        for i in fn.slots:
            if i.k == 1:
                o.append(f"  %{i.s}.def.{i.r[0]} = alloca i1")
                o.append(f"  store i1 false, ptr %{i.s}.def.{i.r[0]}")
            else:
                r = f"%{i.s or 'h'}.{i.r[0]}"
                o.append(f"  {r} = alloca {lt(i.t)}")
                o.append(f"  store {lt(i.t)} zeroinitializer, ptr {r}")
        for b in fn.blocks:
            if b.label != "entry" and b.label != "":
                o.append(b.label + ":")
            for i in b.code:
                self.lower_ins(fn, i)
        o.append("}")

    def lower_ins(self, fn: IFn, i: Ins) -> None:
        op = i.op
        o = self.out
        if op == "raw":
            o.append("  " + i.s)
        elif op == "br":
            o.append(f"  br label %{i.b[0]}")
        elif op == "cbr":
            o.append(f"  br i1 {i.a[0].v}, label %{i.b[0]}, label %{i.b[1]}")
        elif op == "check":
            o.append(f"  br i1 {i.a[0].v}, label %{fn.cold[i.x if i.x != '' else i.s]}, label %{i.b[0]}")
        elif op == "phi":
            o.append(f"  %t{i.r[0]} = phi {lt(i.t)} {', '.join([f'[{i.a[j].v}, %{i.b[j]}]' for j in range(len(i.a))])}")
        elif op == "ovf":
            r = i.r
            o.append(f"  %t{r[0]} = call {{i64, i1}} @llvm.{CHECKED[i.s]}.with.overflow.i64(i64 {i.a[0].v}, i64 {i.a[1].v})")
            o.append(f"  %t{r[1]} = extractvalue {{i64, i1}} %t{r[0]}, 0")
            o.append(f"  %t{r[2]} = extractvalue {{i64, i1}} %t{r[0]}, 1")
        elif op == "select":
            x = i.a[1]
            y = i.a[2]
            o.append(f"  %t{i.r[0]} = select i1 {i.a[0].v}, {lt(x.t)} {x.v}, {lt(y.t)} {y.v}")
        elif op == "ret":
            o.append(f"  ret {lt(i.a[0].t)} {i.a[0].v}" if len(i.a) > 0 else "  ret void")
        elif op == "ret.none":
            o.append("  ret void" if fn.f.ret == "None" else "  ret ptr null")
        elif op == "raise":
            o.append(f"  call void @pys_raise(ptr {i.a[0].v}, ptr {i.a[1].v})")
            o.append("  unreachable")
        elif op == "unreachable":
            o.append("  unreachable")
        elif op == "rt":
            f = self.rtfns[i.s]
            ll = f.ll
            vs = [ll[j + 1] + " " + i.a[j].v for j in range(len(i.a))]
            if i.k > 0 and i.s == "dict.new":
                # the key kind of a dict created empty: what its first use showed (0 if nothing
                # did; refine made a tuple key's descriptor a string constant)
                h = self.holes[i.k]
                vs[0] = f"i64 {self.key_kind(targs(h)[0]) if h != '' else '0'}"
            c = self.invoke(f"call {ll[0]} @{f.sym}({', '.join(vs)})", i)
            o.append("  " + c if ll[0] == "void" else f"  %t{i.r[0]} = {c}")
        elif op == "call":
            c = self.invoke(f"call {lt(i.t)} {i.s}({', '.join([lt(v.t) + ' ' + v.v for v in i.a])})", i)
            o.append("  " + c if i.t == "None" else f"  %t{i.r[0]} = {c}")
        elif op == "init":
            o.append("  " + self.invoke(f"call void @init.{i.s}()", i))
        elif op == "list.load":
            # the item of a list at an index within its length (listget): l->a[index], as runtime.c
            # lays a List out ({len, cap, a}), in the 8-byte slot pys_list_get would have returned
            r = i.r
            o.append(f"  %t{r[1]} = getelementptr inbounds {{i64, i64, ptr}}, ptr {i.a[0].v}, i64 0, i32 2")
            o.append(f"  %t{r[2]} = load ptr, ptr %t{r[1]}")
            o.append(f"  %t{r[3]} = getelementptr inbounds i64, ptr %t{r[2]}, i64 {i.a[1].v}")
            o.append(f"  %t{r[0]} = load i64, ptr %t{r[3]}")
        elif op == "landing":
            r = i.r
            o.append(f"  %t{r[0]} = landingpad {{ ptr, i32 }} catch ptr null")
            o.append(f"  %t{r[1]} = extractvalue {{ ptr, i32 }} %t{r[0]}, 0")
            o.append(f"  store ptr %t{r[1]}, ptr {i.a[0].v}")
            o.append(f"  br label %{i.b[0]}")
        elif op == "throw":
            o.append(f"  call void @pys_throw(ptr {i.a[0].v})")
            o.append("  unreachable")
        elif op == "exc.match":
            o.append(f"  %t{i.r[0]} = call i64 @pys_exc_in(ptr {i.a[0].v}, ptr {i.a[1].v})")
            o.append(f"  %t{i.r[1]} = icmp ne i64 %t{i.r[0]}, 0")
        else:
            fail(f"internal error: no lowering for IR op {op}", 0)

    def invoke(self, c: str, i: Ins) -> str:
        # the call c of op i, an invoke if the exception passes made it one (Ins.b: [next, landing])
        return c if len(i.b) == 0 else f"invoke{c[4:]} to label %{i.b[0]} unwind label %{i.b[1]}"

    # ---- the IR's check (PYSTACHY_IRCHECK=1) and its effect summaries, once the program is built
    def verify(self, fn: IFn, eh: bool) -> None:
        # PYSTACHY_IRCHECK=1: fn is well formed. Every op is in IROPS, an rt op's key in RUNTIME;
        # a raw op is one LLVM instruction that is no call (calls are rt, call and init ops, whose
        # effects are known), no phi and no terminator, and call and init ops call compiled
        # functions; every block ends with its one terminator; branches go to blocks of fn; a phi
        # starts its block, and its predecessors branch there; each op holds exactly the numbers
        # its lowering prints (Ins.r), and no number or label is above IFn.n. Exceptions (once the
        # passes of eh_ir have run, eh): a landing op is alone in its block, which only the unwind
        # edges of invokes reach, and every invoke's unwind edge goes to one; in a block that a
        # try statement covers, no call that may raise is left a call, nor a raise or throw
        at: dict[str, int] = {}
        lands: dict[str, bool] = {}
        for b in fn.blocks:
            if len(b.code) > 0 and b.code[0].op == "landing":
                lands[b.label] = True
        for i in fn.slots:
            if i.op != "slot" or len(i.r) != 1:
                self.bad_ir(fn, fn.blocks[0], f"a {i.op} op among the slots, with {len(i.r)} numbers")
            if i.r[0] > fn.n:
                self.bad_ir(fn, fn.blocks[0], f"the slot of {i.s} numbered {i.r[0]}, above IFn.n ({fn.n})")
        for j in range(len(fn.blocks)):
            l = fn.blocks[j].label
            if l in at:
                self.bad_ir(fn, fn.blocks[j], "a second block of that name")
            if l.startswith("L") and int(l[1:]) > fn.n:
                self.bad_ir(fn, fn.blocks[j], f"a label above IFn.n ({fn.n})")
            at[l] = j
        succ: list[list[str]] = []
        for b in fn.blocks:
            out: list[str] = []
            for j in range(len(b.code)):
                i = b.code[j]
                if i.op not in IROPS:
                    self.bad_ir(fn, b, f"unknown op {i.op}")
                inv = len(i.b) == 2 and (i.op == "rt" or i.op == "call" or i.op == "init")
                if ("T" in IROPS[i.op] or inv) != (j == len(b.code) - 1):
                    self.bad_ir(fn, b, f"a terminator in the middle, at {i.op}" if j < len(b.code) - 1 else f"no terminator, last {i.op}")
                if i.op == "landing" and j > 0:
                    self.bad_ir(fn, b, "a landing op after other ops")
                if inv and i.b[1] not in lands:
                    self.bad_ir(fn, b, f"an invoke whose unwind edge goes to {i.b[1]}, which is no landing block")
                for l in i.b[:1] if inv else i.b if i.op != "phi" else i.b[:0]:
                    if l in lands:
                        self.bad_ir(fn, b, f"a branch to the landing block {l}, which only unwind edges may reach")
                if eh and b.handler != "" and (i.op == "raise" or i.op == "throw" or (not inv and (i.op == "rt" or i.op == "call" or i.op == "init") and self.opfx(i, fn.fa) & FXBIT["R"] != 0)):
                    self.bad_ir(fn, b, f"{i.op} {i.s} may raise, in a block {b.handler} covers, but goes to no landing block")
                if i.op == "phi" and j > 0 and b.code[j - 1].op != "phi":
                    self.bad_ir(fn, b, "a phi after other ops")
                if i.op == "rt" and i.s not in self.rtfns:
                    self.bad_ir(fn, b, f"no RUNTIME entry for {i.s}" if i.s not in RUNTIME else f"{i.s}, which runtime() did not declare")
                n = self.nums(i)
                if len(i.r) != n:
                    self.bad_ir(fn, b, f"{i.op} {i.s} with {len(i.r)} numbers, where its lowering prints {n}")
                for x in i.r:
                    if x > fn.n:
                        self.bad_ir(fn, b, f"{i.op} {i.s} numbered {x}, above IFn.n ({fn.n})")
                if i.op == "raw":
                    # one LLVM instruction that loads, stores or computes: not a call, a phi, a
                    # terminator or a label (its first word, after the "%x = " of a value it defines)
                    w = i.s[i.s.find(" = ") + 3 :] if i.s.startswith("%") and " = " in i.s else i.s
                    w = w[: w.find(" ")] if " " in w else w
                    if w in LLNOTRAW or w.endswith(":") or "\n" in i.s:
                        self.bad_ir(fn, b, f"LLVM text that must be an op: {i.s}")
                if (i.op == "call" and i.s not in self.fll) or (i.op == "init" and "@init." + i.s not in self.fll):
                    self.bad_ir(fn, b, f"a call of {i.s}, which is not compiled")
                if i.op != "phi":
                    out.extend(i.b)
                if i.op == "check":
                    ck = i.x if i.x != "" else i.s
                    out.append(fn.cold[ck] if ck in fn.cold else f"(none for {ck})")
            if len(b.code) == 0:
                self.bad_ir(fn, b, "no terminator")
            for l in out:
                if l not in at or l == "entry":
                    self.bad_ir(fn, b, f"a branch to {l}, which is no block of it")
            succ.append(out)
        for b in fn.blocks:
            for i in b.code:
                if i.op == "phi":
                    for l in i.b:
                        if l not in at or b.label not in succ[at[l]]:
                            self.bad_ir(fn, b, f"a phi from {l}, which does not branch there")

    def nums(self, i: Ins) -> int:
        # how many numbers op i defines (%tN): what its lowering prints
        if i.op == "ovf":
            return 3
        if i.op == "list.load":
            return 4
        if i.op == "landing" or i.op == "exc.match":
            return 2
        if i.op == "phi" or i.op == "select":
            return 1
        if i.op == "rt":
            return 0 if self.rtfns[i.s].sig[0] == "None" else 1
        if i.op == "call":
            return 0 if i.t == "None" else 1
        return 0

    def bad_ir(self, fn: IFn, b: Blk, what: str) -> None:
        fail(f"internal error: bad IR in {fn.f.ll}, block {b.label or '(unnamed)'}: {what}", 0)

    def effects(self) -> None:
        # each function's effect summary (IFn.fx): the letters of its ops, where a call or an init
        # counts with its callee's summary; a fixpoint over the call graph, from no letters
        calls: list[list[int]] = []
        for fn in self.fns:
            m = 0
            cs: list[int] = []
            for b in fn.blocks:
                for i in b.code:
                    if i.op == "raw":
                        m |= rawfx(i.s, fn.fa)
                    elif i.op == "call" and i.s in self.fll:
                        cs.append(self.fll[i.s])
                    elif i.op == "init" and "@init." + i.s in self.fll:
                        cs.append(self.fll["@init." + i.s])
                    else:
                        m |= self.opfx(i, fn.fa)
            fn.fx = m & ~FXBIT["N"]
            calls.append(cs)
        more = True
        while more:
            more = False
            for j in range(len(self.fns)):
                m = self.fns[j].fx
                for x in calls[j]:
                    m |= self.fns[x].fx
                if m != self.fns[j].fx:
                    self.fns[j].fx = m
                    more = True

    def opfx(self, i: Ins, fa: dict[str, bool]) -> int:
        # the effects of op i (FX bits) of a function whose field addresses are fa (IFn.fa): a
        # call's and an init's are its callee's summary (IFn.fx: every letter until effects has
        # computed it, and if the callee is not compiled), a raw op's what its text does (rawfx)
        if i.op == "call" or i.op == "init":
            c = i.s if i.op == "call" else "@init." + i.s
            return self.fns[self.fll[c]].fx if c in self.fll else FXALL
        if i.op == "rt":
            # (an exception, E, may be an object of an exception class, whose __str__ and __repr__ run)
            f = self.rtfns[i.s]
            return FXALL if f.q and ("O" in i.x or ("E" in i.x and len(self.xcls) > 0)) else f.fx
        if i.op == "raw":
            return rawfx(i.s, fa)
        return self.opfxs[i.op]

    # ---- optimizations (OPTS): passes over an IFn, once the program is built and its effect
    # summaries computed, that rewrite ops into cheaper ones (docs/typed-ir.md 7.1)
    def optimize(self, fn: IFn, on: dict[str, bool]) -> int:
        # run the passes on fn that on turns on; how many ops they rewrote
        n = 0
        if "listget" in on:
            n += self.listget(fn)
        if "dictfuse" in on:
            n += self.dictfuse(fn)
        return n

    def preds(self, fn: IFn) -> dict[str, list[int]]:
        # the blocks that branch to each block of fn, by label, as positions in fn.blocks, once
        # each, and the unwind edges: a block that a try statement covers (Blk.handler, which
        # eh_ir has not made invokes yet) goes to its landing block, where an op of it that
        # raises goes. A check's raising edge is left out: its cold block raises, ending the
        # program or, covered itself, going to a landing block (an unwind edge of its own)
        pl: dict[str, list[int]] = {}
        for b in fn.blocks:
            pl[b.label] = []
        for j in range(len(fn.blocks)):
            code = fn.blocks[j].code
            for l in code[len(code) - 1].b:
                if j not in pl[l]:
                    pl[l].append(j)
            h = fn.blocks[j].handler
            if h != "" and h in pl and j not in pl[h]:
                pl[h].append(j)
        return pl

    def listget(self, fn: IFn) -> int:
        # Unchecked list reads in sequence loops. The test a seq loop makes of a list leads to a
        # block (Loop.tests) where the loop's index (Loop.idx) is within the list's length. A
        # list.get of that list at that index, on the one path from there with no op between
        # that may shorten a list (wL, or U: user code), needs no bounds check: it becomes a
        # list.load, which lowers to an inline load. The path goes only to blocks that one
        # branch leads to, so that no other path reaches the read: not a handler's either,
        # whose code (after a landing block, which only unwind edges reach, see preds) joins
        # this path only after its try statement or at a loop's test, where paths meet. How
        # many reads it rewrote
        some = False
        for lp in fn.loops:
            for s in lp.seqs:
                some = some or is_list(s.t)
        if not some:
            return 0
        at: dict[str, int] = {}
        for j in range(len(fn.blocks)):
            at[fn.blocks[j].label] = j
        pl = self.preds(fn)
        bad = FXBIT["wL"] | FXBIT["U"]
        n = 0
        for lp in fn.loops:
            for k in range(len(lp.tests) if lp.kind == "seq" else 0):
                s = lp.seqs[k]
                l = lp.tests[k] if is_list(s.t) else ""
                steps = 0
                while l != "" and steps < len(fn.blocks):
                    steps += 1
                    code = fn.blocks[at[l]].code
                    l = ""
                    for j in range(len(code)):
                        i = code[j]
                        if i.op == "rt" and i.s == "list.get" and i.a[0].v == s.v and i.a[1].v == lp.idx[k]:
                            i.op = "list.load"
                            i.s = ""
                            i.r = [i.r[0], fn.n + 1, fn.n + 2, fn.n + 3]  # (the inline load's address arithmetic)
                            fn.n += 3
                            n += 1
                            break
                        if self.opfx(i, fn.fa) & bad != 0:
                            break
                        if j == len(code) - 1 and (i.op == "br" or i.op == "cbr" or i.op == "check") and len(pl[i.b[0]]) == 1:
                            l = i.b[0]  # (a cbr's: the next sequence's test, in a zip)
        return n

    def dictfuse(self, fn: IFn) -> int:
        # Dict lookup fusion. A dict.has or a dict.getitem of key k in dict d finds k's entry; a
        # dict.getitem or a dict.set of the same d and k after it, where k is known to be in d,
        # can reuse that entry while no dict changes: the has or getitem becomes a dict.find
        # (the entry, or -1) or a dict.entry (the entry, or a KeyError), the getitem after it a
        # dict.val (the entry's value) and the set a dict.entry_set (which moves no entry). k is
        # in d after a getitem, and where the test of a has's result is true. A forward pass over
        # the blocks in order keeps the lookups that hold at the end of each block (Lookup, by
        # position in looks: True where k is known to be in d), from the blocks that branch to a
        # block, and none from a later one (a loop's back edge) nor in a landing block, which
        # unwind edges reach (preds): what holds where an op raises is not what holds at the end
        # of its block (a getitem that raised KeyError ends its block knowing k in d), so a
        # handler's code knows only its own lookups, and so does the code after its try
        # statement, where the handler's end joins. An op with wD or U, and a set that reuses no
        # entry, ends them all. d and k must be the same values (canon). At most
        # LOOKUPS hold at once (the oldest gives way), and a block's state is dropped once the
        # last block it branches to has read it, so that the work and the memory grow linearly
        # with the function. How many ops it rewrote
        some = False
        for b in fn.blocks:
            for i in b.code:
                some = some or (i.op == "rt" and (i.s == "dict.has" or i.s == "dict.getitem"))
        if not some:
            return 0
        pl = self.preds(fn)
        vs = Values(fn, pl)
        looks: list[Lookup] = []
        has: dict[str, int] = {}  # a has's result -> its lookup
        cond: dict[str, int] = {}  # a test of it (icmp ne/eq 0, and xor true of one) -> the lookup
        pos: dict[str, bool] = {}  # and whether it is true where k is in d
        # (a block shares the state it starts with, and copies it before it changes it: own)
        none: dict[int, bool] = {}
        outs: list[dict[int, bool]] = []
        last = [-1] * len(fn.blocks)  # the last block after it that each block branches to
        for j in range(len(fn.blocks)):
            for p in pl[fn.blocks[j].label]:
                if p < j:
                    last[p] = j
        bad = FXBIT["wD"] | FXBIT["U"]
        n = 0
        for j in range(len(fn.blocks)):
            b = fn.blocks[j]
            st = none
            own = False
            ps = pl[b.label]
            back = len(b.code) > 0 and b.code[0].op == "landing"  # (only unwind edges reach it: none holds)
            for p in ps:
                back = back or p >= j  # (a loop's back edge: none holds)
            for x in range(len(ps) if not back else 0):
                if x > 0 and len(st) == 0:
                    break
                # what holds on the branch from block ps[x]: a cbr on a has's test tells whether k is in d
                e = outs[ps[x]]
                t = fn.blocks[ps[x]].code[len(fn.blocks[ps[x]].code) - 1]
                if t.op == "cbr" and t.b[0] != t.b[1] and t.a[0].v in cond and cond[t.a[0].v] in e:
                    c = cond[t.a[0].v]
                    e = e.copy()
                    if (b.label == t.b[0]) == pos[t.a[0].v]:
                        e[c] = True
                    else:
                        e.pop(c)
                if x == 0:
                    st = e
                else:
                    if not own:
                        st = st.copy()
                        own = True
                    for c in [c for c in st]:
                        if c not in e:
                            st.pop(c)
                        elif not e[c]:
                            st[c] = False
            for x in range(len(b.code)):
                i = b.code[x]
                if i.op == "rt" and (i.s == "dict.has" or i.s == "dict.getitem" or i.s == "dict.set"):
                    d = self.canon(vs, i.a[0].v)
                    k = self.canon(vs, i.a[1].v)
                    m = -1
                    for c in st:
                        if st[c] and looks[c].d == d and looks[c].k == k:
                            m = c
                    if m >= 0 and i.s != "dict.has":
                        # reuse the entry lookup m found
                        if looks[m].e == 0:
                            fn.n += 1
                            looks[m].e = fn.n
                        ev = Val(f"%t{looks[m].e}", "int")
                        if i.s == "dict.getitem":
                            self.runtime("pys_dict_val")
                            i.s = "dict.val"
                            i.a = [i.a[0], ev]
                        else:
                            self.runtime("pys_dict_entry_set")
                            i.s = "dict.entry_set"
                            i.a = [i.a[0], ev, i.a[2]]
                        n += 1
                    elif i.s == "dict.set":
                        st = none
                        own = False
                    else:
                        if not own:
                            st = st.copy()
                            own = True
                        if len(st) >= LOOKUPS:
                            o = len(looks)
                            for c in st:
                                o = c if c < o else o
                            st.pop(o)
                        st[len(looks)] = i.s == "dict.getitem"
                        if i.s == "dict.has":
                            has[f"%t{i.r[0]}"] = len(looks)
                        looks.append(Lookup(i, j, x, d, k))
                elif i.op == "raw" and i.k > 0:
                    # %c = icmp ne i64 %r, 0 of a has's result (k in d; eq: k not in d), %c = xor i1 %t, true of one (not)
                    s = i.s
                    o = s.find(" = ") + 3 if len(cond) + len(has) > 0 else 0
                    if len(has) > 0 and s.endswith(", 0") and (s.startswith("icmp ne i64 ", o) or s.startswith("icmp eq i64 ", o)):
                        r = s[o + 12 : len(s) - 3]
                        if r in has:
                            cond[f"%t{i.k}"] = has[r]
                            pos[f"%t{i.k}"] = s.startswith("icmp ne ", o)
                    elif len(cond) > 0 and s.endswith(", true") and s.startswith("xor i1 ", o):
                        r = s[o + 7 : len(s) - 6]
                        if r in cond:
                            cond[f"%t{i.k}"] = cond[r]
                            pos[f"%t{i.k}"] = not pos[r]
                elif len(st) > 0 and self.opfx(i, vs.fn.fa) & bad != 0:
                    st = none
                    own = False
            outs.append(st if last[j] > j else none)
            for p in ps:
                if p < j and last[p] == j:
                    outs[p] = none
        # the lookups whose entry an op reuses: a has becomes a find (and k in d is its entry + 1,
        # which is not 0), a getitem an entry and a val; each adds one op to its block, before
        # the next lookup of the block (shift: how many it has added)
        blk = -1
        shift = 0
        for f in looks:
            if f.e == 0:
                continue
            if f.blk != blk:
                blk = f.blk
                shift = 0
            code = fn.blocks[f.blk].code
            x = f.x + shift
            shift += 1
            i = f.op
            if code[x] is not i:
                self.bad_ir(fn, fn.blocks[f.blk], f"dictfuse lost the lookup of %t{f.e}")
            if i.s == "dict.has":
                self.runtime("pys_dict_find")
                fi = Ins("rt", "int", "dict.find")
                fi.a = [i.a[0], i.a[1]]
                fi.r = [f.e]
                code[x] = fi
                ad = Ins("raw", "", f"%t{i.r[0]} = add i64 %t{f.e}, 1")
                ad.k = i.r[0]
                code.insert(x + 1, ad)
            else:
                self.runtime("pys_dict_entry")
                en = Ins("rt", "int", "dict.entry")
                en.a = [i.a[0], i.a[1]]
                en.r = [f.e]
                code.insert(x, en)
                self.runtime("pys_dict_val")
                i.s = "dict.val"
                i.a = [i.a[0], Val(f"%t{f.e}", "int")]
            n += 1
        return n

    def canon(self, vs: Values, v: str) -> str:
        # the canonical value of value v (Values): ops with the same canonical value compute
        # equal values (as long as no back edge comes between them). A raw op's load reads what
        # the store or load of the same address that comes last before it, on the one path back,
        # stored or read; another raw op, or an rt op that only computes (it may raise, but reads
        # no memory but strings', allocates nothing and does no I/O), computes what the first op
        # of its text, with canonical operands, computed; any other value is its own. It recurses
        # once for each link of the chain of values it follows, so a value it reaches below
        # CANON_DEPTH calls is its own (a long chain, of k = k ^ 1 in straight-line code, would
        # overflow the native compiler's stack)
        if v in vs.cn:
            return vs.cn[v]
        if vs.depth >= CANON_DEPTH:
            vs.cn[v] = v
            return v
        vs.depth += 1
        r = v
        w = vs.at[int(v[2:])] if v.startswith("%t") and v[2:].isdigit() else -1
        if w >= 0:
            i = vs.fn.blocks[w // vs.stride].code[w % vs.stride]
            if i.op == "rt":
                if self.rtfns[i.s].fx & ~FXBIT["R"] == 0 and not self.rtfns[i.s].q:
                    r = self.same(vs, v, f"rt {i.s} {', '.join([self.canon(vs, a.v) for a in i.a])}")
            else:
                s = i.s[i.s.find(" = ") + 3 :]
                if s.startswith("load "):
                    x = self.reaching(vs, self.addr(vs, s[s.rfind(" ") + 1 :]), w // vs.stride, w % vs.stride)
                    if x != "":
                        r = self.canon(vs, x)
                else:
                    # the text with each operand %tN canonical
                    t: list[str] = []
                    a = 0
                    b = s.find("%t")
                    while b >= 0:
                        e = b + 2
                        while e < len(s) and s[e].isdigit():
                            e += 1
                        t.append(s[a:b])
                        t.append(self.canon(vs, s[b:e]) if e > b + 2 and (e == len(s) or s[e] == "," or s[e] == " ") else s[b:e])
                        a = e
                        b = s.find("%t", a)
                    t.append(s[a:])
                    r = self.same(vs, v, "".join(t))
        vs.depth -= 1
        vs.cn[v] = r
        return r

    def same(self, vs: Values, v: str, t: str) -> str:
        # the first value of the computation t (Values.same): v, if it is the first
        if t in vs.same:
            return vs.same[t]
        vs.same[t] = v
        vs.text[v] = t
        return v

    def addr(self, vs: Values, a: str) -> str:
        # the canonical address of address a: a slot (%name.N) and a global (@name) are their own
        return self.canon(vs, a) if a.startswith("%t") and a[2:].isdigit() else a

    def reaching(self, vs: Values, a: str, j: int, x: int) -> str:
        # the value that the load at position x of block j reads from canonical address a: the
        # value stored or read by the last store or load of a before it, on the one path back
        # through blocks that a single branch leads to (not to a landing block's predecessor, which
        # an unwind edge leaves at an op that raised, before the ops after it, as a store to a
        # that the walk would find from its end: preds), or "" if an op between may write a's
        # memory (a slot's: only a store to it; a global's: a store to it, or an op with wG;
        # another's: a store that may alias it, or an op with wL wD wO), or no such op is found
        # within REACH ops (each load would otherwise walk back over the whole function: a
        # value that is not found is only its own canonical value)
        slot = a.startswith("%") and "." in a
        glob = a.startswith("@")
        heap = not slot and not glob
        end = " " + a  # (how a slot's or a global's load or store ends)
        stop = FXBIT["wG"] if glob else RAWW
        steps = 0
        while True:
            code = vs.fn.blocks[j].code
            for y in range(x - 1, -1, -1):
                steps += 1
                if steps > REACH:
                    return ""
                i = code[y]
                if i.op != "raw":
                    if not slot and self.opfx(i, vs.fn.fa) & stop != 0:
                        return ""
                    continue
                s = i.s
                st = s.startswith("store ")
                if not st and (i.k == 0 or not s.startswith("load ", s.find(" = ") + 3)):
                    continue
                if not heap:
                    if s.endswith(end):
                        return s[s.find(" ", 6) + 1 : s.rfind(", ptr ")] if st else f"%t{i.k}"  # (store T V, ptr A)
                    continue
                p = s[s.rfind(" ") + 1 :]
                q = self.addr(vs, p)
                if q == a:
                    return s[s.find(" ", 6) + 1 : s.rfind(", ptr ")] if st else f"%t{i.k}"
                if st and not p.startswith("@") and "." not in p and not self.disjoint(vs, a, q):
                    return ""
            ps = vs.pl[vs.fn.blocks[j].label]
            if len(ps) != 1 or ps[0] >= j or (len(code) > 0 and code[0].op == "landing"):
                return ""  # (a landing block's predecessors reach it where an op raised, not from their end)
            j = ps[0]
            x = len(vs.fn.blocks[j].code)

    def disjoint(self, vs: Values, a: str, b: str) -> bool:
        # whether canonical addresses a and b are fields of different classes or at different
        # indices (getelementptr %C.<class>, ptr <object>, i32 0, i32 <index>): never the same memory
        ta = vs.text.get(a, "")
        tb = vs.text.get(b, "")
        if not ta.startswith("getelementptr %C.") or not tb.startswith("getelementptr %C."):
            return False
        return ta[: ta.find(",")] != tb[: tb.find(",")] or ta[ta.rfind(",") :] != tb[tb.rfind(",") :]

    def eh_ir(self, fn: IFn) -> None:
        # fn has try statements: its blocks' exception edges (Blk.handler) become LLVM's, once the
        # effect summaries say which calls may raise. A raise or throw that a landing block covers
        # branches to the code after it, with the exception in its try's slot as the landing op
        # stores it: no unwinder, which takes a microsecond. (A raise's exception is made as
        # pys_raise makes it, from its kind and message: in a program that has a try, no raise op
        # has the line of a SyntaxError as its kind, see raise_stmt.) A call a landing block covers
        # that may raise (R) becomes an invoke whose unwind edge goes there, and ends its block (a
        # phi after it names the last part as its predecessor). A landing block no invoke goes to
        # is dropped (the code after it may still be reached from a raise), and a function left
        # without one has no personality
        lands: dict[str, Ins] = {}
        for b in fn.blocks:
            if len(b.code) > 0 and b.code[0].op == "landing":
                lands[b.label] = b.code[0]
        used: dict[str, bool] = {}
        ren: dict[str, str] = {}
        blocks: list[Blk] = []
        raises = FXBIT["R"]
        for b in fn.blocks:
            if b.handler == "":
                blocks.append(b)
                continue
            code = b.code
            t = code[-1]
            if t.op == "raise" or t.op == "throw":
                lp = lands[b.handler]
                code = code[: len(code) - 1]
                ex = t.a[0].v
                if t.op == "raise":
                    fn.n += 1
                    i = Ins("rt", "exc", "exc.new")
                    i.a = [t.a[0], t.a[1], Val("null", "str")]
                    i.r = [fn.n]
                    self.runtime("pys_exc_new")
                    code.append(i)
                    ex = f"%t{fn.n}"
                code.append(Ins("raw", "", f"store ptr {ex}, ptr {lp.a[0].v}"))
                br = Ins("br", "", "")
                br.b = [lp.b[0]]
                code.append(br)
            cur = b
            cur.code = []
            for j in range(len(code)):
                i = code[j]
                cur.code.append(i)
                if j < len(code) - 1 and (i.op == "rt" or i.op == "call" or i.op == "init") and self.opfx(i, fn.fa) & raises != 0:
                    fn.n += 1
                    i.b = [f"L{fn.n}", b.handler]
                    used[b.handler] = True
                    blocks.append(cur)
                    cur = Blk(i.b[0])
                    cur.handler = b.handler
            blocks.append(cur)
            if cur is not b:
                ren[b.label] = cur.label
        fn.blocks = []
        for b in blocks:
            if b.label in lands and b.label not in used:
                continue
            fn.blocks.append(b)
            for i in b.code:
                if i.op != "phi":
                    break
                for j in range(len(i.b)):
                    if i.b[j] in ren:
                        i.b[j] = ren[i.b[j]]
        fn.pads = len(used) > 0
        if fn.pads:
            self.runtime("pys_personality")

    def subclass_problem(self, st: Node) -> str:
        # why class statement st, which names bases, cannot be compiled, or "": only an exception
        # class can, whose one base is a builtin exception class or an exception class of the
        # program declared before it
        if st.kids[1].kind == "typeparams":
            return "generic classes (class C[T]) are not supported"
        b = self.exc_base(st.kids[1])
        if b == "" and len(st.kids) == 2 and st.kids[1].kind == "name" and short(st.kids[1].s) == "object":
            return UNSUPPORTED["subclass"] + " (the module may have rebound the name 'object' before this statement)"
        if b == "" and st.kids[1].kind == "name" and st.kids[1].s in self.classes:
            return UNSUPPORTED["subclass"] + " (only an exception class may have a base)"
        if b == "":
            return UNSUPPORTED["subclass"] + " (only an exception class may have a base, which names a builtin exception class or an exception class of the program)"
        if len(st.kids) > 2:
            return "an exception class with more than one base is not supported"
        if b not in self.classes and (EXCEPTIONS.get(b, "-") == "-" or exc_derives(b, "SyntaxError")):
            return f"deriving from {b} is not supported"
        if len(st.kids[0].kids) > 1:
            return f"an exception class with a decorator (@{st.kids[0].kids[1].s}) is not supported"
        return ""

    def exc_base(self, b: Node) -> str:
        # the exception class that b, the base of a class statement, names: a class of the program
        # or a builtin one (IOError and EnvironmentError are OSError; builtins.X and os.error
        # too), else ""
        s = b.s
        if b.kind == "attr" and b.kids[0].kind == "name" and self.imported(b.kids[0].s) == "builtins" and is_excname(b.s):
            s = b.s
        elif b.kind == "attr" and b.kids[0].kind == "name" and self.imported(b.kids[0].s) == "os" and b.s == "error":
            s = "OSError"
        elif b.kind != "name":
            return ""
        if s in self.classes:
            return s if self.classes[s].exc != "" else ""
        if is_excname(s):
            return "OSError" if s == "IOError" or s == "EnvironmentError" else s
        return ""

    def inherit(self, ci: ClassInfo) -> None:
        # an exception class has the methods of its base that it does not define: the same
        # functions, compiled for the base (its objects begin as the base's do), but for a class
        # method that uses cls, which is compiled again with cls naming this class (unless a
        # default value of it needs evaluating when its def runs, or the base is another
        # module's: cls_bound rejects its calls).
        # It may define __init__, __str__ and __repr__ again (str() and repr() call those of the
        # object's class, see exc_helpers), but no other method: calls are not dispatched on the
        # object's class
        if ci.base not in self.classes:
            return
        b = self.classes[ci.base]
        for m in b.methods:
            f = b.methods[m]
            if m not in ci.methods and f.clsuse and f.mod == ci.mod and len([x for x in f.defaults if not is_const(x) and x.kind != "noann"]) == 0:
                self.line = f.node.line
                self.lib = f.mod != ""
                self.selfcls = ci.name
                ci.methods[m] = self.declare_fn(clone(f.orig), ci.name)
                self.selfcls = ""
                self.lib = False
                ci.methods[m].mod = f.mod
                self.lazy[ci.methods[m].ll] = ci.methods[m]  # (compiled only if called: cls(...) may not fit this class)
            elif m not in ci.methods:
                ci.methods[m] = f
            elif m != "__init__" and m != "__str__" and m != "__repr__":
                self.line = ci.methods[m].node.line
                self.err(f"method '{m}' of '{short(ci.name)}' overrides that of '{short(b.methods[m].cls)}': only __init__, __str__ and __repr__ may be overridden")

    def derives(self, c: str, base: str) -> bool:
        # is c, a class of the program or a builtin exception class, base or derived from it
        while c in self.classes:
            if c == base:
                return True
            c = self.classes[c].base
        return c in EXCBASES and exc_derives(c, base)

    def class_problem(self, m: Mod, st: Node) -> str:
        # why a class of an imported module cannot be declared, or "": its methods need
        # annotated parameters, and its body may hold only fields, methods and a docstring
        if len(st.kids) > 2 or (len(st.kids) > 1 and (dc_args(st.kids[1]).startswith("!") or self.imported(st.kids[1].s) != "dataclasses.dataclass")):
            return f"its decorator @{short(st.kids[1].s)} is not supported"
        for b in st.kids[0].kids:
            if b.kind == "def":
                ps = b.kids[0].kids
                deco = b.kids[3].s if len(b.kids) == 4 and len(b.kids[3].kids) == 0 else ""
                static = deco == "staticmethod"
                if len(b.kids) > 3 and ((not static and deco != "classmethod") or (b.s.startswith("__") and b.s.endswith("__"))) and not self.stub(m, b):
                    return f"method {b.s}() has a decorator"  # (an @overload stub's calls are the error: see declare_fn)
                if len(ps) == 0 and not static:
                    return f"method {b.s}() has no {'cls' if deco != '' else 'self'} parameter"
                for i in range(len(ps)):
                    if ps[i].kind != "param":
                        return f"method {b.s}() takes *args or **kwargs"
                    if (i > 0 or static) and ps[i].kids[0].kind == "noann":
                        return f"parameter '{ps[i].s}' of method {b.s}() has no type annotation"
            elif not (b.kind == "annassign" and b.kids[0].kind == "name") and not (b.kind == "assign" and len(b.kids) == 2 and b.kids[0].kind == "name") and b.kind != "pass" and not (b.kind == "expr" and (b.kids[0].kind == "str" or b.kids[0].kind == "ellipsis")):
                return "its body holds statements other than fields, methods and a docstring"
        return ""

    # ---- definition time. CPython runs an imported module's def and class statements when its
    # code runs, used or not. Pystachy compiles the defaults and class bodies it supports there and
    # leaves the rest out, which must run no code of the program, and applies no decorator. What
    # that code reads must be bound (Loader.deftime; a variable that may not be is checked here).
    def eager(self, e: str, why: str, does: str) -> None:
        # e: what the code Pystachy leaves out (for the reason why) may run when CPython does that
        if e != "":
            self.err(f"{why}; CPython {does} when module '{self.curfn.mod}' is imported, and {e}")

    def decorators(self, d: Node, decos: list[Node], local: dict[str, str]) -> str:
        # the decorators of def or class statement d: only those that run no code of the program
        # then (local: the names a class body has bound, "p" a property); the outermost one's name
        key = ""
        inst = False  # (object.__new__ has made an object of the class)
        for x in decos:
            self.line = x.line
            root = x.s.split(".")[0]
            key = self.imported(x.s) if "$" in root else x.s if root in PYBUILTINS else ""
            key = key[9:] if key.startswith("builtins.") else key
            if short(root) in local:
                key = "property" if local[short(root)] == "p" and x.s[len(root) :] in [".setter", ".getter", ".deleter"] else ""
            ok = x.s == "async" or (("f" if d.kind == "def" else "c") in INERT_DECOS.get(key, "") and (not inst or ("o" in INERT_DECOS[key] and "__setattr__" not in self.body_names(d))))
            inst = inst or key == "object.__new__"
            e = f"'{short(root)}' may not be the builtin then" if "$" in root and short(root) in PYBUILTINS and key == "" else ""
            e = e if e != "" or len(x.kids) == 0 or key == "dataclasses.dataclass" else f"it calls {short(x.s)}()"
            for a in x.kids[0].kids[1:] if len(x.kids) > 0 and key == "dataclasses.dataclass" else []:
                # (@dataclass(...) tests the truth of each option)
                e = e if e != "" else self.effect(a.kids[0], {}, 1) if a.kind == "kw" else "it takes no positional argument"
            if not ok or e != "":
                self.err(f"unsupported decorator @{short(x.s)}: CPython applies it when module '{self.curfn.mod}' is imported" + (f", and {e}" if e != "" else ""))
        return key

    def class_effect(self, st: Node, why: str) -> None:
        # class statement st, which Pystachy leaves out (for the reason why): CPython evaluates its
        # decorators and bases, runs its body, creates the class and applies the decorators
        c = st.kids[0] if st.kind == "subclass" else st
        does = f"creates class {short(c.s)}"
        self.decorators(c, c.kids[1:], {})
        for b in st.kids[1:] if st.kind == "subclass" else []:
            self.line = b.line
            x = b.kids[0] if b.kind == "index" or b.kind == "kw" else b
            p = self.path_of(x)
            e = "it passes a metaclass" if b.kind == "kw" and b.s == "metaclass" else "" if b.kind == "typeparams" else self.effect(x, {}, 2 if b.kind == "kw" else 0)
            if e == "" and b.kind != "kw" and x.kind == "name" and x.s in self.hooks:
                h = self.chooks.get(st.line, self.hooks[x.s])  # (a nested class: its base's latest)
                e = f"it calls {h}()" if h != "" else ""
            elif e == "" and b.kind != "kw" and b.kind != "typeparams" and not ("$" not in p and p in PYBUILTINS) and self.imported(p) == "":
                e = f"its base '{short(p)}' may not be a class"  # (its __mro_entries__ may run)
            self.eager(e if e != "" or b.kind != "index" else self.effect(b.kids[1], {}, 2), why, does)
        self.body_effect(c.kids[0].kids, {}, why, f"runs this statement of the body of class {short(c.s)}")

    def body_effect(self, body: list[Node], local: dict[str, str], why: str, does: str) -> None:
        # the statements of a class body Pystachy leaves out (local: the names it has bound)
        for b in body:
            self.line = b.line
            k = b.kind
            e = ""
            if k == "def":
                local[b.s] = "p" if self.decorators(b, b.kids[3:], local) == "property" else "f"
                for p in b.kids[0].kids:
                    self.eager(self.effect(p.kids[1], local, 0), why, does)
            elif k == "class" or k == "subclass":
                self.class_effect(b, "nested classes are not supported")
                local[short(b.s)] = "f"
            elif k == "if":
                self.eager(self.effect(b.kids[0], local, 1), why, does)
                self.body_effect(b.kids[1].kids, local, why, does)
                self.body_effect(b.kids[2].kids, local, why, does)
            elif k == "assign" or k == "annassign" or k == "augassign" or k == "expr":
                # (CPython calls a class attribute's __set_name__, each unpacked one's too)
                ts: list[str] = []
                u = 0 if k == "expr" else 2 if k == "augassign" else 1
                for t in b.kids[:-1] if k == "assign" else b.kids[:1] if k == "augassign" or len(b.kids) == 3 else []:
                    u = 2 if t.kind == "tuple" or t.kind == "list" else u
                    e = e if e != "" or not (has_kind(t, "attr") or has_kind(t, "index") or has_kind(t, "slice")) else "it assigns to an attribute or item, which may run code"
                    names_in(t, ts)
                e = e if e != "" or k != "augassign" else self.effect(b.kids[0], local, 2)
                if e == "" and (k != "annassign" or len(b.kids) == 3):
                    e = self.effect(b.kids[-1], local, u)
                for nm in ts:
                    local[nm] = ""
                self.eager(e, why, does)
            elif k == "del":
                for t in b.kids:
                    e = e if e != "" or (t.kind == "name" and "$" not in t.s and t.s in local) else "it deletes what the class body has not bound"
                    local.pop(t.s, "")
                self.eager(e, why, does)
            elif k != "pass":
                k = "import" if k.endswith("import") else k
                self.eager(f"Pystachy does not check what {'an' if k[0] in 'aeiou' else 'a'} '{k}' statement there runs", why, does)

    def body_names(self, c: Node) -> dict[str, bool]:
        # the names class statement c's body binds, by assignment or def
        out: dict[str, bool] = {}
        collect(c.kids[0].kids, out)
        for b in c.kids[0].kids:
            if b.kind == "def":
                out[b.s] = True
        return out

    def hook(self, st: Node) -> None:
        # class statement st, in the order statements run: chooks[its line], what creating it calls
        # of its bases (by their class statements so far); hooks[its name], what subclassing or
        # subscripting it calls: the __init_subclass__ or __class_getitem__ it or its bases bind
        h = ""
        for b in st.kids[1:] if st.kind == "subclass" else []:
            x = b.kids[0] if b.kind == "index" else b
            if h == "" and x.kind == "name":
                h = self.hooks.get(x.s, "")
        self.chooks[st.line] = h
        own = self.body_names(st.kids[0] if st.kind == "subclass" else st)
        for nm in ["__init_subclass__", "__class_getitem__"]:
            if nm in own:
                h = f"{short(st.s)}.{nm}"
        self.hooks[st.s] = h
        self.cnodes[st.line] = st

    def path_of(self, n: Node) -> str:
        # the dotted name an attribute chain spells (its first name qualified), or ""
        if n.kind == "name":
            return n.s
        if n.kind == "attr" and self.path_of(n.kids[0]) != "":
            return self.path_of(n.kids[0]) + "." + n.s
        return ""

    def objects(self, t: str, use: int) -> bool:
        # may a value of type t be an object of one of the program's classes (use 2: or hold one)
        return len([x for x in t.replace("[", ",").replace("]", ",").split(",") if x in self.classes and (use >= 2 or x == t)]) > 0

    def pure(self, q: str) -> bool:
        # does a call of q, a builtin or a builtin module's function given builtin values, run no
        # code of the program and change nothing (or is q a builtin module's value)
        i = self.imported(q)
        return ("$" not in q and q in PURE) or i in PURE or i in MODATTRS or i.startswith("math.") or i.startswith("os.path.")

    def effect(self, e: Node, local: dict[str, str], use: int) -> str:
        # what evaluating e, which Pystachy leaves out, may run of the program's code ("" if
        # nothing): it may read names (checked here if they may be unbound, as in read()) and apply
        # builtin operations to values of builtin types. use: then CPython 0 stores the value, 1 may
        # call its methods (an operand, an argument, a truth test, a class attribute's
        # __set_name__), 2 its items' too (a set item, a dict key), 3 may call it too (an argument
        # of a builtin function). local: the class body's names
        k = e.kind
        p = self.path_of(e) if k == "name" or k == "attr" else ""
        q = self.imported(p)
        if use == 3 and (k == "lambda" or (q != "" and not self.pure(p))):
            return f"it passes {short(p) if p != '' else 'a lambda'} to a function that may call it"
        if k in INERT or is_const(e) or q != "" or (k == "lambda" and e.s == "") or (k == "badattr" and e.s.endswith("cannot be used as a value")):
            return ""
        if k == "name":
            if (e.chk or self.foreign(e.s)) and e.s in self.gflag:
                self.flagged[e.s] = True
                self.guard(self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{e.s}.def')}, true"), self.unbound(e.s))
            t = self.gtypes.get(e.s, "")
            if use == 3 and (e.s in self.funcs or e.s in self.hooks or ("$" not in e.s and (e.s in local or (e.s in PYBUILTINS and e.s not in PURE)))):
                return f"it passes {short(e.s)} to a function that may call it"
            if use == 0 or "$" not in e.s or e.s in self.funcs or e.s in self.hooks or e.s in self.noneglobals or (t != "" and not self.objects(t, use)):
                return ""
            return f"'{short(e.s)}' may be an object of one of the program's classes, whose methods CPython calls then"
        if k == "attr" and e.kids[0].kind == "name" and (e.kids[0].s in self.hooks or ("$" not in e.kids[0].s and e.kids[0].s in local)):
            # (a class's attribute: a method, or a field of a class Pystachy compiles, or what? A
            # field's class may define __get__, which reading it calls)
            ci = self.classes[e.kids[0].s] if e.kids[0].s in self.classes else ClassInfo("", e)
            t = ci.ftypes.get(e.s, "")
            if use < 3 and (e.s in ci.methods or ((t != "" or use == 0) and not self.objects(t, use if use > 0 else 1))):
                return self.effect(e.kids[0], local, 0)
            return f"it passes {short(p)} to a function that may call it" if use == 3 else f"'{short(p)}' may be an object of one of the program's classes, whose methods CPython calls then"
        if k == "call":
            f = e.kids[0]
            q = self.path_of(f)
            wrap = "$" not in q and (q == "classmethod" or q == "staticmethod" or q == "property")
            # (a method of a builtin value that only reads it)
            rt = f.kids[0].kind if f.kind == "attr" and f.kids[0].kind in ["str", "int", "float"] else self.gtypes.get(self.path_of(f.kids[0]), "") if f.kind == "attr" else ""
            method = rt in ["str", "int", "float", "bool"] or (rt.split("[")[0] in ["list", "dict", "tuple"] and f.s in ["get", "keys", "values", "items", "copy", "count", "index"] and not self.objects(rt, 2))
            if not wrap and not method and not self.pure(q):
                return f"it calls {short(q)}()" if q != "" else "it calls a function"
            r = self.effect(f.kids[0], local, 1) if method else ""
            for a in e.kids[1:]:
                r = r if r != "" else self.effect(a.kids[0] if a.kind == "kw" else a, local, 0 if wrap else 3)
            return r
        if (k == "index" or k == "slice") and e.kids[0].kind == "name" and self.hooks.get(e.kids[0].s, "") != "":
            return f"it calls {self.hooks[e.kids[0].s]}()"
        if k == "lambda" or k == "badattr":
            return e.s if k == "badattr" else "Pystachy does not check the default values of its lambda"
        if k not in ["attr", "index", "slice", "binop", "unary", "cmp", "boolop", "ifexp", "fstr", "fmt", "tuple", "list", "set", "dict", "starred", "dstar"]:
            return f"Pystachy does not check what {'a comprehension' if k.endswith('comp') else 'an assignment expression' if k == 'walrus' else 'a ' + k + ' expression'} there runs"
        for i in range(len(e.kids)):
            # (an operand or set item: 2; a truth test or an attribute's object: 1; the container
            # indexed: its items too if the item is used, called if it is; a tuple's, list's or
            # dict's item, an if-else's or boolop's value: as the whole, unpacked: its items too)
            u = 2 if k != "attr" else 1
            if k == "ifexp" or k == "boolop":
                u = 1 if k == "ifexp" and i == 0 else use if k == "ifexp" or use > 1 else 1
            elif (k == "index" or k == "slice") and i == 0:
                u = 3 if use == 3 else 1 if use == 0 else 2
            elif k == "tuple" or k == "list" or (k == "dict" and i % 2 == 1):
                u = use if use > 1 else 0
            elif k == "starred" or k == "dstar":
                u = use if use > 2 else 2
            r = self.effect(e.kids[i], local, u)
            if r != "":
                return r
        return ""

    def partly(self, e: Node, use: int) -> str:
        # (part of) a default value Pystachy cannot compile, used as effect() says: CPython evaluates
        # it, Pystachy the items of displays it can compile; what the rest may run (effect)
        if self.default_problem(e, "") == "":
            t = self.expr(e, "").t if not is_const(e) else ""
            return "an item may be an object of one of the program's classes, whose methods CPython calls then" if use > 0 and self.objects(t, use) else ""
        r = ""
        for i in range(len(e.kids) if e.kind in ["tuple", "list", "set", "dict"] else 0):
            r = r if r != "" else self.partly(e.kids[i], 2 if e.kind == "set" or (e.kind == "dict" and i % 2 == 0) else use)
        return r if e.kind in ["tuple", "list", "set", "dict"] else self.effect(e, {}, use)

    def program(self, mods: list[Mod]) -> str:
        # the modules in the order their code may first run, the main program last
        tops: list[list[Node]] = []
        for m in mods:
            self.scan_imports(m.body.kids)
            self.eh = self.eh or has_try(m.body.kids)
        for m in mods:
            m.body.kids = self.typing_forms(m, m.body.kids, False)
            for i in range(len(m.body.kids)):
                st = m.body.kids[i]
                if st.kind == "subclass" and len(st.kids) == 2 and self.nt_base(st.kids[1]):
                    m.body.kids[i] = st.kids[0]  # class P(NamedTuple): a class (see nt_class)
                    self.nts[st.s] = True
                elif self.typevar_def(st):
                    self.typevars.append(st.kids[0].s)
                    m.body.kids[i] = mk("pass", "", st.line, [])
        for m in mods:
            for st in m.body.kids:
                self.line = st.line
                why = ""
                if st.kind == "class" or st.kind == "subclass":
                    self.hook(st)
                if st.kind == "subclass":
                    why = self.subclass_problem(st)
                    if why == "" and m.name != "":
                        why = self.class_problem(m, st.kids[0])
                elif st.kind == "class" and m.name != "":
                    why = self.class_problem(m, st)
                if why != "" and m.name == "":
                    self.err(why)
                if why != "":
                    # a class of an imported module that Pystachy cannot compile: an error only
                    # where the program uses it
                    self.unsupported[st.s] = f"class {st.s} is not supported: {why}"
                elif st.kind == "subclass":
                    # an exception class (subclass_problem)
                    if st.s in self.classes:
                        self.err(f"redefinition of class '{st.s}' is not supported")
                    ci = ClassInfo(st.s, st.kids[0])
                    ci.mod = m.name
                    ci.base = self.exc_base(st.kids[1])
                    ci.exc = self.classes[ci.base].exc if ci.base in self.classes else ci.base
                    self.classes[st.s] = ci
                elif st.kind == "class":
                    if st.s in self.classes:
                        self.err(f"redefinition of class '{st.s}' is not supported")
                    self.classes[st.s] = ClassInfo(st.s, st)
                    self.classes[st.s].mod = m.name
                    if len(st.kids) > 1 and self.imported(st.kids[1].s) == "dataclasses.dataclass" and dc_args(st.kids[1]).startswith("!"):
                        self.err(dc_args(st.kids[1])[1:])
                    self.classes[st.s].kwonly = len(st.kids) > 1 and dc_args(st.kids[1]) == "kw"
                    if len(st.kids) > 1 and self.imported(st.kids[1].s) != "dataclasses.dataclass":
                        self.err(f"unsupported decorator @{st.kids[1].s}" + (" (import dataclass from dataclasses)" if st.kids[1].s == "dataclass" else ""))
                    if len(st.kids) > 2:
                        self.err(f"unsupported decorator @{st.kids[2].s}")
        for m in mods:
            top: list[Node] = []
            for st in m.body.kids:
                self.line = st.line
                if st.kind == "def":
                    if st.s in self.funcs or st.s in self.classes:
                        self.err(f"redefinition of '{st.s}' is not supported")
                    self.lib = m.name != ""
                    self.funcs[st.s] = self.declare_fn(st, "")
                    self.lib = False
                    self.funcs[st.s].mod = m.name
                    top.append(mk("defaults", st.s, st.line, []))
                elif (st.kind == "class" or st.kind == "subclass") and st.s not in self.classes:
                    top.append(mk("lclass", st.s, st.line, []))  # (a class it leaves out: class_effect)
                elif st.kind == "class" or st.kind == "subclass":
                    for d in self.classes[st.s].node.kids[0].kids:
                        if d.kind == "def":
                            self.line = d.line
                            if d.s in self.classes[st.s].methods:
                                self.err(f"redefinition of method '{st.s}.{d.s}' is not supported")
                            self.lib = m.name != ""
                            self.selfcls = st.s
                            self.classes[st.s].methods[d.s] = self.declare_fn(d, st.s)
                            self.selfcls = ""
                            self.lib = False
                            self.classes[st.s].methods[d.s].mod = m.name
                    top.append(mk("cdefaults", st.s, st.line, []))
                else:
                    top.append(st)
            tops.append(top)
        for ci in self.classes.values():
            self.inherit(ci)
        for ci in self.classes.values():
            self.selfcls = ci.name
            self.declare_fields(ci)
            self.selfcls = ""
            for f in ci.methods.values():
                self.check_special(f)
        for m in mods:
            self.cvar_stores(m.body.kids)
        for m in mods:
            imps: list[str] = []
            all_imports(m.body.kids, imps)
            self.deps[m.name] = " ".join(imps)
        # the import graph's strongly connected components (see user_call)
        num: dict[str, int] = {}
        low: dict[str, int] = {}
        stack: list[str] = []
        for m in mods:
            if m.name not in num:
                self.scc(m.name, num, low, stack)
        # each module's functions and classes, in the order they were declared
        mfns: dict[str, list[FnInfo]] = {}
        mcls: dict[str, list[ClassInfo]] = {}
        for m in mods:
            mfns[m.name] = []
            mcls[m.name] = []
        for f in self.funcs.values():
            mfns[f.mod].append(f)
        for ci in self.classes.values():
            mcls[ci.mod].append(ci)
        for i in range(len(mods)):
            self.flow_program(tops[i], mods[i].name, mfns[mods[i].name], mcls[mods[i].name])
        for nm in self.gflag:
            if nm in self.funcs or nm in self.classes:
                self.global_var(f"@g.{nm}.def", "i1")
        for m in mods:
            # a module global that module code only sets to None (an optional accelerator's
            # fallback, _json = None, or a cache a function fills, _varsub = None) and that is
            # assigned before any read is the constant None; a compiled function that gives it
            # another value is an error (in the program's module, one whose global statement
            # binds it is left to the advice to annotate it)
            vals: dict[str, list[Node]] = {}
            none_assigns(m.body.kids, vals)
            for nm in vals:
                nones = True
                for v in vals[nm]:
                    if v.kind != "None":
                        nones = False
                if nones and nm not in self.gflag and nm in self.mvars and (m.name != "" or nm not in m.fnglobal):
                    self.noneglobals[nm] = True
        for m in mods:
            for st in m.body.kids if m.name != "" else []:
                # an imported module's constants (NAME = literal) are typed before any module code
                # compiles: a module it imports, which imports it back, may read them first
                if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s not in self.gtypes and st.kids[0].s not in self.noneglobals:
                    k = st.kids[1].kids[0].kind if st.kids[1].kind == "unary" and is_const(st.kids[1]) else st.kids[1].kind  # (-1, -2.5)
                    if k == "int" or k == "float" or k == "str":
                        self.declare(st.kids[0].s, k)
                    elif k == "True" or k == "False":
                        self.declare(st.kids[0].s, "bool")
        for m in mods:
            self.inits[m.name] = FnInfo("<module>", "@init." + m.name if m.name != "" else "@main.init", m.body, "")
            self.inits[m.name].mod = m.name
            self.mfile[m.name] = m.path[2:] if m.path.startswith("./") else m.path
        self.modlevel = True
        for i in range(len(mods)):
            self.function(self.inits[mods[i].name], tops[i])
            self.inited[mods[i].name] = True
        self.modlevel = False
        # the functions and methods of imported modules are compiled only if the program calls
        # them, as templates are (a function compiled early, see early, is compiled already)
        for f in self.funcs.values():
            if f.mod != "" and not f.generic:
                self.lazy[f.ll] = f
            elif not f.generic and f.ll not in self.compiled:
                self.function(f, f.node.kids[2].kids)
        for ci in self.classes.values():
            for f in ci.methods.values():
                if f.cls != ci.name:
                    continue  # (an exception class's base's)
                if ci.mod != "" and f.ll not in self.lazy:
                    self.lazy[f.ll] = f
                elif f.ll not in self.lazy and f.ll not in self.compiled:
                    self.function(f, f.node.kids[2].kids)
        # generate on demand: dataclass methods that were called, and helpers for classes that
        # appear inside containers (which can make more of both necessary). Each pass compiles,
        # in the order of lazy, the functions called by the time it gets to them: it takes their
        # positions from wake (call_fn adds them), so that it costs what it compiles
        lz = [x for x in self.lazy.values()]
        for i in range(len(lz)):
            self.lazyat[lz[i].ll] = i
            if lz[i].ll in self.called:
                hpush(self.wake, i)
        done: dict[str, bool] = {}
        helped: dict[str, bool] = {}
        xmade: dict[str, bool] = {}
        while True:
            before = len(done) + len(helped) + len(xmade)
            for c in [x for x in self.ocls]:
                if c not in helped:
                    helped[c] = True
                    self.obj_helpers(c)
            for c in [x for x in self.xcls]:
                if c not in xmade:
                    xmade[c] = True
                    self.exc_helpers(c)
            at = -1
            later: list[int] = []
            while len(self.wake) > 0:
                i = hpop(self.wake)
                if i <= at:
                    later.append(i)  # called after the pass went by: the next pass compiles it
                elif lz[i].ll not in done:
                    at = i
                    done[lz[i].ll] = True
                    if lz[i].ll not in self.compiled:
                        self.function(lz[i], lz[i].node.kids[2].kids)
            for i in later:
                hpush(self.wake, i)
            if len(done) + len(helped) + len(xmade) == before:
                break
        for nm in self.flagged:
            if nm not in self.gtypes and nm not in self.funcs and nm not in self.classes:
                self.global_var(f"@g.{nm}.def", "i1")  # (a variable no compiled code assigns)
        # the whole program is built: its functions are printed in the order they were completed
        for j in range(len(self.fns)):
            self.fll[self.fns[j].f.ll] = j
        if len(NONUMS) + len(NOVALS) + len(NOLABELS) > 0:
            fail("internal error: an op changed the lists all ops start with", 0)
        chk = os.getenv("PYSTACHY_IRCHECK", "") == "1"
        dump = os.getenv("PYSTACHY_IRFX", "") == "1"
        on = optimizations()
        if chk:
            for fn in self.fns:
                self.verify(fn, False)
        if self.eh or len(on) > 0 or chk or dump:
            # the passes and eh_ir read the effect summaries (eh_ir: which calls may raise); the IR
            # check computes them too, so that the tests run effects even with every pass off
            self.effects()
        if len(on) > 0:
            # (before eh_ir: a block that a try statement covers keeps its exception edge to the
            # landing block, Blk.handler, which the passes count, see preds)
            changed = False
            for fn in self.fns:
                if self.optimize(fn, on) > 0:
                    changed = True
                    if chk:
                        self.verify(fn, False)
            if changed and dump:
                self.effects()  # (what the passes left: tests/ir/*.fx pin them)
        for fn in self.fns if self.eh else self.fns[:0]:
            if len(fn.tries) > 0:
                self.eh_ir(fn)
                if chk:
                    self.verify(fn, True)
        if dump:
            for fn in self.fns:
                print(f"{fn.f.ll}: {fxs(fn.fx)}".rstrip(), file=sys.stderr)
        for fn in self.fns:
            self.lower(fn)
            # its LLVM text is all that is left to print: its IR goes (its summary, IFn.fx, stays)
            fn.blocks = []
            fn.slots = []
            fn.loops = []
            fn.cold = {}
            fn.fa = {}
        for op in ["eq", "cmp", "repr"]:
            self.dispatch(op)
        hdr: list[str] = ["; generated by pystachy"]
        for ci in self.classes.values():
            ts = [lt(ci.ftypes[x]) for x in ci.fields]
            for _ in range(ci.nflag):
                ts.append("i1")
            hdr.append(f"%C.{ci.name} = type {{{', '.join(ts)}}}")
        hdr.extend(self.globs)
        roots = ", ".join([f"ptr {g}" for g in self.gcroots])
        hdr.append(f"@pys.roots = private constant [{len(self.gcroots)} x ptr] [{roots}]")
        hdr.extend(self.consts)
        hdr.extend(self.out)
        for k in self.rtfns:
            hdr.append(self.rtfns[k].decl)
        # pys_init gets the GC roots: main's frame address bounds the stack scan (it also
        # covers @main.init if inlined here) and the table of pointer-typed globals
        hdr.append(runtime_decl("init"))
        hdr.append(runtime_decl("finish"))
        hdr.append(runtime_decl("frameaddress"))
        if self.eh:
            hdr.append(runtime_decl("eh_on"))
        hdr.append("define i32 @main(i32 %argc, ptr %argv) {")
        hdr.append("  %sb = call ptr @llvm.frameaddress.p0(i32 0)")
        hdr.append(f"  call void @pys_init(i32 %argc, ptr %argv, ptr %sb, ptr @pys.roots, i64 {len(self.gcroots)})")
        if self.eh:
            hdr.append("  call void @pys_eh_on()")  # (from now on, the runtime raises exceptions)
        hdr.append("  call void @main.init()")
        hdr.append("  call void @pys_finish()")
        hdr.append("  ret i32 0")
        hdr.append("}")
        return "\n".join(hdr) + "\n"

    # ---- definite assignment, before code generation: CPython raises UnboundLocalError or
    # NameError when a read finds its variable unassigned. Reads that cannot are plain loads;
    # the others (Node.chk) test an "is assigned" flag kept only for the variables they read.
    def flow_program(self, top: list[Node], mod: str, mfns: list[FnInfo], mcls: list[ClassInfo]) -> None:
        # one module: its top-level code, functions (mfns) and classes' methods (mcls)
        self.flowmod = mod
        fns: list[FnInfo] = []
        for f in mfns:
            fns.append(f)
        for ci in mcls:
            for f in ci.methods.values():
                if f.cls == ci.name:
                    fns.append(f)
        gl: dict[str, bool] = {}
        collect(top, gl)
        for f in fns:
            decl: dict[str, bool] = {}
            asg: dict[str, bool] = {}
            globals_in(f.node.kids[2].kids, decl)
            collect(f.node.kids[2].kids, asg)
            for nm in decl:
                if nm in asg:
                    if nm not in gl:
                        self.fglobals[nm] = True
                    gl[nm] = True
        # one binding per name: a function, a class, an import or a variable
        for nm in gl:
            if nm in self.funcs or nm in self.classes or (nm in self.imports and not self.imports[nm].startswith("__future__")):
                self.err(f"'{nm}' is bound both as a variable and as a function, class or import (not supported)")
        for nm in self.imports:
            if nm in self.funcs or nm in self.classes:
                self.err(f"'{nm}' is bound both by an import and by a def or class (not supported)")
        for nm in gl:
            self.mvars[nm] = True
        # def and class statements bind their names when they run: calls that may come first are checked
        for f in mfns:
            gl[f.name] = True
        for ci in mcls:
            gl[ci.name] = True
        mfl = Flow(gl, {})
        for st in top:
            # (a statement inside a compound one calls user code only if the compound one does)
            if not mfl.called and self.user_call(st):
                mfl.called = True
                mfl.call = dict(mfl.defd)
            self.fl_stmt(mfl, st)
        for nm in mfl.marks:
            self.gflag[nm] = True
        # functions run only from module code: globals assigned before its first call into user
        # code stay assigned while any function runs
        safe = mfl.call if mfl.called else gl
        dels: dict[str, bool] = {}
        deleted(top, dels)
        if mod != "" and " dead" not in mfl.defd:
            # an imported module's functions also run after its code, from other modules' code
            after: dict[str, bool] = {}
            for nm in safe:
                if nm in mfl.defd:
                    after[nm] = True
            safe = after
        if mod != "":
            for nm in gl:
                if nm not in safe or nm in dels:
                    self.late[nm] = True
                    self.gflag[nm] = True
        for f in fns:
            body = f.node.kids[2].kids
            loc: dict[str, bool] = {}
            decl: dict[str, bool] = {}
            local_names(body, loc)
            globals_in(body, decl)
            # the analysis looks up only the names the body mentions, and each name's state is
            # independent of the others': it tracks those alone, not every global of the module
            refs: dict[str, bool] = {}
            for st in body:
                name_nodes(st, refs)
            tracked: dict[str, bool] = {}
            defd: dict[str, bool] = {}
            for nm in refs:
                if nm in gl or nm in loc:
                    tracked[nm] = True
                if nm in gl and nm in safe and nm not in dels and (nm not in loc or nm in decl):
                    defd[nm] = True
            fdels: dict[str, bool] = {}
            deleted(body, fdels)
            for nm in f.params:
                defd[nm] = True
                if nm in fdels:
                    tracked[nm] = True  # (a parameter that del unbinds)
            fl = Flow(tracked, defd)
            self.fl_stmts(fl, body)
            for nm in fl.marks:
                if (nm in loc or nm in fdels) and nm not in decl:
                    f.uflags[nm] = True
                else:
                    self.gflag[nm] = True
        for ci in mcls:
            self.fl_fields(ci)

    def fl_fields(self, ci: ClassInfo) -> None:
        # a field that may be read before __init__ assigns it gets an "is assigned" flag, so the
        # read raises AttributeError as in CPython instead of seeing 0 or null. The flags follow
        # the class's own fields; an exception class's struct begins with its base's, flags
        # included, since the base's methods work on its objects. Its constructor sets the hidden
        # fields; super().__init__() assigns what the base's __init__ surely does (and exposes self
        # if that lets it escape), as the constructor does when it calls the base's __init__
        if ci.flowed:
            return
        ci.flowed = True
        fl = Flow({}, {})
        for f in ci.fdefault:
            fl.defd["." + f] = True
        nb = 0
        if ci.base in self.classes:
            b = self.classes[ci.base]
            self.fl_fields(b)
            own = [f for f in ci.fields if f not in b.ftypes]
            ci.fields = [f for f in b.fields]
            for f in b.fields:
                ci.ftypes[f] = b.ftypes[f]  # (the places of its base's base's flags too)
            for k in range(b.nflag):
                ci.fields.append(f" {b.name}.{k}")  # (the place of one of the base's flags)
                ci.ftypes[ci.fields[-1]] = "bool"
            ci.fields.extend(own)
            for i in range(len(ci.fields)):
                ci.fpos[ci.fields[i]] = i
            for f in b.fflag:
                ci.fflag[f] = b.fflag[f]
            for f in b.fields:
                if f not in b.fflag:
                    fl.sup.append(f)
            fl.leak = b.leak
            fl.base = shown(ci.base)
            nb = len(ci.fields) - len(own)
        for f in ci.fields:
            if f.startswith(" "):
                fl.defd["." + f] = True
        fl.fields = ci.fields
        if ci.exc != "" and ("__init__" not in ci.methods or ci.methods["__init__"].cls != ci.name):
            # its constructor calls the __init__ of its base (or of none)
            for f in fl.sup:
                fl.put("." + f)
            fl.exposed()
            ci.leak = fl.leak
        elif ci.methods["__init__"].node.kids[0].kind == "noann":
            if not self.is_dc(ci.name):
                fl.exposed()
        else:
            init = ci.methods["__init__"]
            asg: dict[str, bool] = {}
            collect(init.node.kids[2].kids, asg)
            if init.params[0] not in asg:
                # (if __init__ rebinds self, no assignment is known to reach the new object)
                fl.me = init.params[0]
                self.fl_stmts(fl, init.node.kids[2].kids)
            fl.exposed()
            ci.leak = fl.escaped
        for f in ci.fields:
            if (f in fl.unsafe or ci.name + "." + f in self.cvars) and f not in ci.fflag:  # (a class variable's: has the object its own value)
                if ci.fpos[f] < nb and f in fl.unsafe:
                    # (the base's code, which reads it with no flag to test)
                    self.line = ci.node.line
                    self.err(f"{short(ci.name)}.__init__ may leave field '{f}' of {short(ci.base)} unassigned where it is read: assign it, or call super().__init__(...) first")
                ci.fflag[f] = len(ci.fields) + ci.nflag
                ci.nflag += 1

    def default_home(self, ci: ClassInfo, fl: str) -> ClassInfo:
        # the class whose class body binds class attribute fl of ci: ci's, or the base's that an
        # exception class inherits it from (the same default, which declare_fields copies down;
        # a class body that binds fl again has a default of its own)
        while fl in ci.fdefault and ci.base in self.classes and fl in self.classes[ci.base].fdefault and self.classes[ci.base].fdefault[fl] is ci.fdefault[fl]:
            ci = self.classes[ci.base]
        return ci

    def fl_defaults(self, n: Node) -> list[Node]:
        # the default values a def or class statement evaluates (see hoist)
        out: list[Node] = []
        fs: list[FnInfo] = []
        if n.kind == "defaults":
            fs.append(self.funcs[n.s])
        else:
            ci = self.classes[n.s]
            for fl in ci.fields:
                if fl in ci.fdefault and not is_const(ci.fdefault[fl]) and self.default_home(ci, fl) is ci:
                    out.append(ci.fdefault[fl])
            for f in ci.methods.values():
                if f.cls == ci.name:
                    fs.append(f)
        for f in fs:
            for d in f.defaults:
                if not is_const(d):
                    out.append(d)
        return out

    def scc(self, root: str, num: dict[str, int], low: dict[str, int], stack: list[str]) -> None:
        # Tarjan's algorithm over the import graph (deps) from module root: the modules numbered
        # and not yet in a component are on the stack. The search keeps its path in lists, since
        # a chain of imports can be longer than CPython's recursion limit
        path: list[str] = []
        outs: list[list[str]] = []
        nxt: list[int] = []
        x = root
        enter = True
        while True:
            if enter:
                # enter module x
                num[x] = len(num)
                low[x] = num[x]
                stack.append(x)
                path.append(x)
                outs.append(self.deps.get(x, "").split())
                nxt.append(0)
                enter = False
            a = path[-1]
            if nxt[-1] < len(outs[-1]):
                x = outs[-1][nxt[-1]]
                nxt[-1] += 1
                if x not in num:
                    enter = True
                elif x not in self.comp:
                    low[a] = min(low[a], num[x])
                continue
            # leave module a
            path.pop()
            outs.pop()
            nxt.pop()
            if low[a] == num[a]:
                while True:
                    y = stack.pop()
                    self.comp[y] = a
                    if y == a:
                        break
            if len(path) == 0:
                return
            low[path[-1]] = min(low[path[-1]], low[a])

    def user_call(self, n: Node) -> bool:
        # may running n call a user function, method or constructor? (an import of a user module
        # runs the module's code)
        if n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s in self.funcs or n.kids[0].s in self.classes):
            return True
        if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s in self.classes:
            return True  # C.m(...): a static or class method
        if n.kind == "uimport":
            # it runs a module's code, which can call this module's functions only if it imports
            # this module (circular imports): as this module imports it, only if both are in one
            # strongly connected component of the import graph. A package's own name, before its
            # submodule's, runs nothing
            for x in n.kids:
                if x.s != self.flowmod and self.comp[x.s] == self.comp[self.flowmod]:
                    return True
            return False
        if n.kind == "defaults" or n.kind == "cdefaults":
            for d in self.fl_defaults(n):
                if self.user_call(d):
                    return True
        for k in n.kids:
            if self.user_call(k):
                return True
        return False

    def fl_stmts(self, fl: Flow, body: list[Node]) -> None:
        for st in body:
            self.fl_stmt(fl, st)

    def fl_stmt(self, fl: Flow, n: Node) -> None:
        k = n.kind
        if k == "assign":
            self.fl_expr(fl, n.kids[-1])
            for i in range(len(n.kids) - 1):
                self.fl_target(fl, n.kids[i])
        elif k == "annassign":
            if len(n.kids) == 3:
                self.fl_expr(fl, n.kids[2])
                self.fl_target(fl, n.kids[0])
        elif k == "augassign":
            self.fl_expr(fl, n.kids[0])
            self.fl_expr(fl, n.kids[1])
            self.fl_target(fl, n.kids[0])
        elif k == "if":
            self.fl_expr(fl, n.kids[0])
            mark = len(fl.log)
            self.fl_stmts(fl, n.kids[1].kids)
            then = fl.since(mark)
            fl.undo(mark)
            self.fl_stmts(fl, n.kids[2].kids)
            fl.join(then, mark)
        elif k == "while" or k == "for":
            self.fl_expr(fl, n.kids[0] if k == "while" else n.kids[1])
            dels: dict[str, bool] = {}
            deleted(n.kids[2 if k == "for" else 1].kids, dels)
            for nm in dels:
                fl.drop(nm)  # (a del in the body may run before a read in the next pass)
            mark = len(fl.log)
            btrue = fl.btrue
            bjoin = fl.bjoin
            bany = fl.bany
            bwas = fl.bwas
            bnew = fl.bnew
            unb = fl.unb
            fl.btrue = k == "while" and n.kids[0].kind == "True"
            fl.bjoin = {}
            fl.bany = False
            fl.bwas = {}
            fl.bnew = {}
            fl.unb = []
            if k == "for":
                self.fl_target(fl, n.kids[0])
            self.fl_stmts(fl, n.kids[2 if k == "for" else 1].kids)
            exits = fl.bjoin
            broke = fl.bany
            # (undone before the enclosing loop's fields are back: to that loop, the body changed nothing)
            fl.undo(mark)
            fl.btrue = btrue
            fl.bjoin = bjoin
            fl.bany = bany
            fl.bwas = bwas
            fl.bnew = bnew
            fl.unb = unb
            if n.kids[-1].s == "else":
                # (after the loop only what was assigned before it is surely assigned, less what
                # the else block unbinds: the loop is left at its end or, from a break, in a state
                # that has what was assigned before it. A while True never runs its else block)
                self.fl_stmts(fl, n.kids[-1].kids)
                if k == "while" and n.kids[0].kind == "True":
                    fl.undo(mark)
                else:
                    st = fl.since(mark)
                    fl.undo(mark)
                    fl.join(st, mark)
            if k == "while" and n.kids[0].kind == "True":
                # while True is left only through break: in what the states at its breaks have
                # in common
                if not broke:
                    fl.put(" dead")
                for x in exits:
                    if exits[x]:
                        fl.put(x)
                    else:
                        fl.drop(x)
        elif k == "break":
            for nm in fl.unb:
                fl.drop(nm)
            if fl.btrue and " dead" not in fl.defd:
                fl.fold()
            fl.put(" dead")
        elif k == "continue" or k == "return" or k == "raise":
            for c in n.kids:
                self.fl_expr(fl, c)
            if k == "return":
                fl.exposed()
            fl.put(" dead")
        elif k == "defaults" or k == "cdefaults":
            for d in self.fl_defaults(n):
                self.fl_expr(fl, d)
            fl.put(n.s)
        elif k == "lclass":
            self.fl_expr(fl, self.cnodes[n.line])  # (the reads of a class Pystachy leaves out, also in its methods)
        elif k == "expr" or k == "assert" or k == "del":
            for c in n.kids:
                self.fl_expr(fl, c)
                if k == "del" and c.kind == "name":
                    fl.drop(c.s)  # unbound from here on
        elif k == "with":
            for it in n.kids[:-1]:
                self.fl_expr(fl, it.kids[0])
                if len(it.kids) == 2:
                    self.fl_target(fl, it.kids[1])
            self.fl_stmts(fl, n.kids[-1].kids)
        elif k == "try":
            # an except clause starts from the state before the statement less what the body may
            # have unbound, the else block goes on from the body, and the statement ends in the
            # join of those that end, then the finally block. A copy of that runs as an exception,
            # a break or a return leaves too: it is looked at once more, from the state before the
            # statement less everything the statement may unbind (which a break that runs it may
            # have left too, so what it unbinds is unbound from the start)
            orelse: list[Node] = []
            fin: list[Node] = []
            hasfin = False
            for b in n.kids[1:]:
                if b.kind == "block" and b.s == "else":
                    orelse = b.kids
                elif b.kind == "block":
                    fin = b.kids
                    hasfin = True
            fdels: dict[str, bool] = {}
            deleted(fin, fdels)
            for nm in fdels:
                fl.drop(nm)
                fl.unb.append(nm)  # (a break out of the statement runs the finally block first)
            mark = len(fl.log)
            bdels: dict[str, bool] = {}
            deleted(n.kids[0].kids, bdels)
            self.fl_stmts(fl, n.kids[0].kids)
            self.fl_stmts(fl, orelse)
            for h in n.kids[1:]:
                if h.kind != "except":
                    continue
                st = fl.since(mark)
                fl.undo(mark)
                for nm in bdels:
                    fl.drop(nm)
                self.fl_expr(fl, h.kids[0])  # (its classes are read when an exception gets to it)
                if h.s != "":
                    fl.put(h.s)
                    fl.unb.append(h.s)
                self.fl_stmts(fl, h.kids[1].kids)
                if h.s != "":
                    fl.unb.pop()
                    fl.drop(h.s)
                fl.join(st, mark)
            for nm in fdels:
                fl.unb.pop()
            if hasfin:
                st = fl.since(mark)
                fl.undo(mark)
                dels: dict[str, bool] = {}
                deleted([n], dels)
                for nm in dels:
                    fl.drop(nm)
                self.fl_stmts(fl, fin)
                fl.undo(mark)
                for nm in st:
                    if st[nm]:
                        fl.put(nm)
                    else:
                        fl.drop(nm)
                self.fl_stmts(fl, fin)

    def fl_target(self, fl: Flow, t: Node) -> None:
        if t.kind == "name":
            fl.put(t.s)
        elif t.kind == "attr" and fl.me != "" and t.kids[0].kind == "name" and t.kids[0].s == fl.me:
            fl.put("." + t.s)
        elif t.kind == "tuple":
            for k in t.kids:
                self.fl_target(fl, k)
        else:
            for k in t.kids:
                self.fl_expr(fl, k)

    def fl_expr(self, fl: Flow, e: Node) -> None:
        k = e.kind
        if k == "name":
            if e.s in fl.tracked and e.s not in fl.defd and " dead" not in fl.defd:
                e.chk = True
                fl.marks[e.s] = True
            if e.s == fl.me:
                fl.exposed()
                fl.escaped = True
        elif k == "attr" and fl.me != "" and e.kids[0].kind == "name" and e.kids[0].s == fl.me:
            if "." + e.s not in fl.defd and " dead" not in fl.defd:
                fl.unsafe[e.s] = True
        elif k == "listcomp":
            # [elt for target in iter if cond]: iter is read outside, the rest with target bound
            self.fl_expr(fl, e.kids[2])
            mark = len(fl.log)
            self.fl_target(fl, e.kids[1])
            for i in range(len(e.kids)):
                if i != 1 and i != 2:
                    self.fl_expr(fl, e.kids[i])
            fl.undo(mark)
        elif k == "call":
            c = e.kids[0]
            if c.kind == "attr":
                self.fl_expr(fl, c.kids[0])
            elif c.kind != "name":
                self.fl_expr(fl, c)
            elif (c.s in self.funcs or c.s in self.classes) and c.s in fl.tracked and c.s not in fl.defd and " dead" not in fl.defd:
                c.chk = True
                fl.marks[c.s] = True
            # super().__init__(...) in an exception class's __init__ (fl_fields), or Base.__init__(self, ...)
            sup = fl.me != "" and c.kind == "attr" and c.s == "__init__" and c.kids[0].kind == "call" and c.kids[0].kids[0].kind == "name" and c.kids[0].kids[0].s == "super"
            based = fl.me != "" and c.kind == "attr" and c.s == "__init__" and c.kids[0].kind == "name" and c.kids[0].s == fl.base and len(e.kids) > 1 and e.kids[1].kind == "name" and e.kids[1].s == fl.me
            for i in range(2 if based else 1, len(e.kids)):
                self.fl_expr(fl, e.kids[i])
            if sup or based:
                for f in fl.sup:
                    fl.put("." + f)
                if fl.leak:
                    fl.exposed()
        else:
            for c in e.kids:
                self.fl_expr(fl, c)

    # ---- statements
    def stmts(self, body: list[Node]) -> None:
        for s in body:
            if self.term and self.curfn.inst:
                # after a return, raise, break or continue: in a template's function, where a
                # static test leaves code for other argument types behind one, it is not compiled
                return
            self.stmt(s)

    def obj_helpers(self, c: str) -> None:
        # @o.eq/cmp/repr.<class>: what the runtime's generic ==, ordering and repr do with objects
        # of class c. They are compiled leniently: an operation the class does not support
        # raises TypeError when it runs rather than failing the compilation.
        line = self.classes[c].node.line
        a = mk("name", "a", line, [])
        b = mk("name", "b", line, [])
        op = mk("name", "op", line, [])
        cmp: list[Node] = []
        for o in ["<", "<=", ">"]:
            hit = mk("block", "", line, [mk("return", "", line, [mk("cmp", o, line, [a, b])])])
            cmp.append(mk("if", "", line, [mk("cmp", "==", line, [op, mk("int", str(ORDOP[o]), line, [])]), hit, mk("block", "", line, [])]))
        cmp.append(mk("return", "", line, [mk("cmp", ">=", line, [a, b])]))
        bodies = [[mk("return", "", line, [mk("cmp", "==", line, [a, b])])], cmp,
                  [mk("return", "", line, [mk("call", "", line, [mk("name", "__pys_repr", line, []), a])])]]
        ops = ["eq", "cmp", "repr"]
        self.lenient = True
        for i in range(3):
            f = FnInfo(ops[i], f"@o.{ops[i]}.{c}", self.classes[c].node, "")
            f.params = ["op", "a", "b"] if i == 1 else ["a", "b"]
            f.ptypes = ["int", c, c] if i == 1 else [c, c]
            f.ret = "str" if i == 2 else "bool"
            self.function(f, bodies[i])
        self.lenient = False

    def dispatch(self, op: str) -> None:
        # pys_obj_<op>(class id, [op code,] a, b), called by the runtime for "O<id>" descriptors
        r = "ptr" if op == "repr" else "i64"
        self.out.append(f"define {r} @pys_obj_{op}(i64 %c, {'i64 %op, ' if op == 'cmp' else ''}i64 %a, i64 %b) {{")
        self.out.append("entry:")
        self.out.append("  %pa = inttoptr i64 %a to ptr")
        self.out.append("  %pb = inttoptr i64 %b to ptr")
        self.out.append(f"  switch i64 %c, label %none [{' '.join([f'i64 {self.ocls[c]}, label %k{self.ocls[c]}' for c in self.ocls])}]")
        for c in self.ocls:
            i = self.ocls[c]
            self.out.append(f"k{i}:")
            if op == "repr":
                self.out.append(f"  %r{i} = call ptr @o.repr.{c}(ptr %pa, ptr %pb)")
                self.out.append(f"  ret ptr %r{i}")
            else:
                self.out.append(f"  %r{i} = call i1 @o.{op}.{c}({'i64 %op, ' if op == 'cmp' else ''}ptr %pa, ptr %pb)")
                self.out.append(f"  %z{i} = zext i1 %r{i} to i64")
                self.out.append(f"  ret i64 %z{i}")
        self.out.append("none:")
        self.out.append("  unreachable")
        self.out.append("}")

    def check_special(self, f: FnInfo) -> None:
        # the special methods Pystachy calls implicitly must have the shape it relies on; in an
        # imported module's class, a wrong one is an error where the method is called, as is a
        # method whose declaration failed (f.bad: its types are placeholders)
        if f.name not in SPECIAL or f.bad != "":
            return
        self.line = f.node.line
        spec = SPECIAL[f.name]
        n = int(spec[: spec.find(":")])
        ret = spec[spec.find(":") + 1 :]
        if len(f.params) != n:
            f.bad = f"{f.name} must take {n - 1} argument{'s' if n != 2 else ''} besides self"
        elif f.name == "__bool__" and f.ret != "bool":
            f.bad = f"__bool__ should return bool, returned {tname(f.ret)}"  # (CPython's TypeError)
        elif ret != "" and f.ret != ret and not (f.name == "__len__" and f.ret == "bool"):
            f.bad = f"{f.name} must return {ret}"  # (a bool is an int to len())
        elif f.name == "__format__" and f.ptypes[1] != "str":
            f.bad = "__format__ takes the format spec as a str"
        if f.bad != "" and self.classes[f.cls].mod == "":
            self.err(f.bad)

    def scan_imports(self, body: list[Node]) -> None:
        # every import anywhere in the program, checked up front; the alias table that code
        # generation uses is still filled statement by statement
        for st in body:
            self.line = st.line
            if st.kind == "import":
                for a in st.kids:
                    self.check_import(a)
                    self.imports[a.s] = a.kids[0].s
            for k in st.kids:
                if k.kind == "block":
                    self.scan_imports(k.kids)
                elif k.kind == "except":
                    self.scan_imports(k.kids[1].kids)
            if st.kind == "def" or st.kind == "class":
                self.scan_imports(st.kids[-1].kids if st.kind == "class" else st.kids[2].kids)

    def imported(self, name: str) -> str:
        # what an imported name (possibly dotted) refers to, or ""
        root = name[: name.find(".")] if "." in name else name
        return self.imports[root] + name[len(root) :] if root in self.imports else ""

    def check_import(self, a: Node) -> None:
        mod = a.kids[1].s
        tgt = a.kids[0].s
        if mod not in MODULES and mod != "collections.abc":
            self.err(f"module '{mod}' is not supported (available: {', '.join(MODULES.keys())})")
        if tgt == mod or tgt == mod[: mod.find(".")] or (tgt + ".") == mod[: len(tgt) + 1]:
            return
        x = tgt[len(mod) + 1 :]
        if mod == "__future__":
            if x not in FUTURE:
                self.err(f"future feature {x} is not defined")
        elif mod == "typing" or mod == "collections.abc":
            if x not in (TYPING if mod == "typing" else ABCS):
                self.err(f"cannot import name '{x}' from '{mod}'")
        elif mod == "dataclasses":
            if x != "dataclass":
                self.err(f"dataclasses.{x} is not supported")
        elif not builtin_has(mod, x):
            self.err(f"cannot import name '{x}' from '{mod}': Pystachy's {mod} module has no '{x}'")

    def hidden(self, name: str, v: Val) -> str:
        # a compiler-made global, assigned here
        self.global_var(name, lt(v.t))
        self.emit(f"store {lt(v.t)} {v.v}, ptr {name}")
        return name

    def early_default(self, f: FnInfo, j: int) -> None:
        # a call that leaves out parameter j of f, compiled before f's def statement (in a
        # template's function, or a function compiled early): the global that is to hold the
        # default value is declared now, and the def statement stores the value into it (hoist)
        if f.cls != "" and f.name == "__init__" and f.node.kids[0].kind == "noann":
            # a dataclass's __init__: the class statement evaluates the field's default
            self.class_default(self.classes[f.cls], f.params[j])
            f.dglob[j] = self.classes[f.cls].fglob[f.params[j]]
            return
        t = f.ptypes[j]
        bad = self.default_problem(f.defaults[j], t) if f.mod != "" else ""
        if bad != "":
            f.dglob[j] = "!" + bad
            return
        if t == "":
            t = self.modtype(f.defaults[j], f.mod)
            if t == "" or "?" in t:
                self.err(f"the default value of parameter '{f.params[j]}' of {f.name}() cannot be typed here, before its def statement runs; annotate the parameter")
        self.pending[f"{f.ll}.{j}"] = True
        if t == "None":
            f.dglob[j] = "=None"
            return
        f.dtypes[j] = t
        f.dglob[j] = f"@d.{f.ll[1:]}.{f.params[j]}"
        self.global_var(f.dglob[j], lt(t))

    def class_default(self, ci: ClassInfo, fl: str) -> None:
        # a class-body default read before the class statement runs (see early_default), or a
        # class variable's global: that of the class whose body binds it (default_home), which an
        # exception class deriving from it shares
        h = self.default_home(ci, fl)
        if fl not in h.fglob:
            h.fglob[fl] = f"@d.c.{h.name}.{fl}"
            self.global_var(h.fglob[fl], lt(h.ftypes[fl]))
            self.pending[h.fglob[fl]] = True
        ci.fglob[fl] = h.fglob[fl]

    def hoist(self, f: FnInfo) -> None:
        # Python evaluates default values once, when the def statement runs
        for j in range(len(f.params)):
            d = f.defaults[j]
            early = f"{f.ll}.{j}" in self.pending
            if (f.dglob[j] == "" or early) and not is_const(d):
                t = f.ptypes[j] if f.bad == "" else ""  # (an unsupported annotation is no type)
                self.line = d.line
                bad = self.default_problem(d, t) if f.mod != "" else ""
                if bad != "":
                    # a function of an imported module: the default is an error only where a call
                    # needs it, if evaluating it when the def runs does nothing
                    self.eager(self.partly(d, 0), bad, "evaluates this default value")
                    f.dglob[j] = "!" + bad
                    continue
                v = self.expr(d, t)
                if early:
                    # a call compiled before this statement declared its global (early_default)
                    del self.pending[f"{f.ll}.{j}"]
                    if f.dglob[j] != "=None":
                        self.emit(f"store {lt(f.dtypes[j])} {self.coerce(v, f.dtypes[j]).v}, ptr {f.dglob[j]}")
                    continue
                if v.t == "None" and t == "":
                    f.dglob[j] = "=None"  # a None value is no global: calls pass None
                    continue
                f.dtypes[j] = v.t
                f.dglob[j] = self.hidden(f"@d.{f.ll[1:]}.{f.params[j]}", self.coerce(v, t) if t != "" else v)

    def default_problem(self, e: Node, t: str) -> str:
        # why default value e of a parameter of type t ("": a template's) cannot be compiled, as far
        # as its form shows, or ""
        if e.kind == "name" and (e.s in self.funcs or e.s in self.classes):
            return f"function '{e.s}' cannot be used as a value"
        if e.kind == "name" and e.s in PYBUILTINS and "$" not in e.s:
            return f"the builtin '{e.s}' cannot be used as a value (not supported)"
        if t == "" and (e.kind == "list" or e.kind == "dict") and len(e.kids) == 0:
            return f"cannot infer the type of an empty {e.kind} as a default value; annotate the parameter"
        if e.kind == "badattr":
            return e.s
        if e.kind in UNSUPPORTED:
            return UNSUPPORTED[e.kind]
        for k in e.kids:
            if e.kind == "call" and k is e.kids[0] and k.kind == "name":
                continue  # the function called
            r = self.default_problem(k, "?")
            if r != "":
                return r
        return ""

    def hoist_class(self, ci: ClassInfo) -> None:
        # class-body defaults are evaluated once, when the class statement runs, in body order,
        # and shared. Pystachy has no class scope: names bound earlier in the body are rejected.
        for st in ci.node.kids[0].kids if ci.mod != "" and ci.bad == "" else []:
            if st.kind == "annassign" and len(st.kids) == 3 and st.kids[0].kind == "name":
                why = self.default_problem(st.kids[2], ci.ftypes[st.kids[0].s])
                if why != "":
                    ci.bad = f"class {shown(ci.name)} is not supported: {why}"
        if ci.bad != "":
            # an imported module's class Pystachy cannot compile: an error only where used
            self.class_effect(self.cnodes[ci.node.line], ci.bad)
            return
        bound: dict[str, bool] = {}
        syn = "__init__" in ci.methods and ci.methods["__init__"].node.kids[0].kind == "noann"  # (a dataclass's)
        later = ""
        for st in ci.node.kids[0].kids:
            self.line = st.line
            if st.kind == "annassign" and len(st.kids) == 3 and st.kids[0].kind == "name":
                fl = st.kids[0].s
                self.no_class_names(st.kids[2], bound, ci)
                bound[fl] = True
                t = ci.ftypes[fl]
                u = unopt(t)  # (a default of a T | None field that is not None is a T)
                if self.is_dc(ci.name) and ci.name not in self.nts and not is_const(st.kids[2]) and (is_list(u) or is_dict(u) or self.unhashable(u) or (self.is_dc(u) and u not in self.nts)):
                    self.err(f"mutable default {u} for dataclass field '{fl}' is not allowed")
                for m in ["__set_name__", "__get__", "__set__", "__delete__"] if t in self.classes and not is_const(st.kids[2]) else []:
                    # (__set_name__ runs when CPython creates the class, __get__ too with @dataclass)
                    now = m == "__set_name__" or (m == "__get__" and self.is_dc(ci.name))
                    why = f"a class attribute whose class defines {m} is not supported (CPython calls it {'when it creates the class' if now else 'where the attribute is used'})"
                    if m in self.classes[t].methods and (now or ci.mod == ""):
                        self.err(why)
                    later = later if later != "" or m not in self.classes[t].methods else f"class {shown(ci.name)} is not supported: {why}"
                cv = ci.name + "." + fl in self.cvars  # (a class variable's constant default needs its global too)
                if (cv or not is_const(st.kids[2])) and fl in ci.fglob and ci.fglob[fl] in self.pending:
                    # code compiled before this statement declared its global (class_default)
                    del self.pending[ci.fglob[fl]]
                    self.emit(f"store {lt(t)} {self.coerce(self.expr(st.kids[2], t), t).v}, ptr {ci.fglob[fl]}")
                elif (cv or not is_const(st.kids[2])) and fl not in ci.fglob:
                    ci.fglob[fl] = self.hidden(f"@d.c.{ci.name}.{fl}", self.coerce(self.expr(st.kids[2], t), t))
            elif st.kind == "def":
                f = ci.methods[st.s]
                for d in f.defaults:
                    self.no_class_names(d, bound, ci)
                bound[st.s] = True
                if f.name != "__init__" or not syn:
                    self.hoist(f)
        if syn:
            init = ci.methods["__init__"]
            for j in range(1, len(init.params)):
                init.dglob[j] = ci.fglob.get(init.params[j], "")
        ci.bad = later  # (an imported module's class: an error where the program uses it)

    def no_class_names(self, e: Node, bound: dict[str, bool], ci: ClassInfo) -> None:
        # (the loader leaves a class body's names unqualified where it reads them: qstmts)
        if e.kind == "name" and "$" not in e.s and e.s in bound:
            self.err(f"class attribute '{e.s}' of '{short(ci.name)}' used in a class-body default is not supported")
        for k in e.kids:
            self.no_class_names(k, bound, ci)

    def unhashable(self, t: str) -> bool:
        # a class that defines __eq__ without __hash__ has __hash__ = None in CPython (a NamedTuple
        # has a tuple's)
        return t in self.classes and "__eq__" in self.classes[t].methods and "__hash__" not in self.classes[t].methods and t not in self.nts

    def while_(self, n: Node) -> None:
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        lp = Loop("while", l1, l2, l1, l3)
        self.fn.loops.append(lp)
        after = self.forget(n.kids[1].kids, n.kids[1])
        self.place(l1)
        self.cbr(self.cond(n.kids[0]), l2, l3)
        self.place(l2)
        self.narrow_by(n.kids[0], True)
        brks = self.loop(n.kids[1].kids, lp)
        self.br(l1)
        self.narrowed = after
        # after the loop: what holds where its test is false (never for while True) and at each
        # break that leaves it here (a loop with an else block breaks past it)
        self.narrow_by(n.kids[0], False)
        ends: list[dict[str, bool]] = []
        if n.kids[0].kind != "True":
            ends.append(self.narrowed)
        if n.kids[1].kids is not self.elsekids:
            ends.extend(brks)
        self.narrowed = meet(ends) if len(ends) > 0 else after
        self.place(l3)

    def loop(self, body: list[Node], lp: Loop) -> list[dict[str, bool]]:
        # the body of loop lp: continue jumps to lp.step, break to lp.exit; what narrowed holds at
        # its breaks is returned (see while_)
        if body is self.elsekids:
            lp.exit = self.elsebrk  # the loop of a for/while ... else: break skips the else block
        self.loops.append(lp)
        self.wdepth.append(len(self.exits))
        self.brks.append([])
        self.branch += 1
        self.stmts(body)
        self.branch -= 1
        self.wdepth.pop()
        self.loops.pop()
        r = self.brks.pop()
        if body is self.elsekids:
            self.elsebrks = r
        return r

    def leave(self, depth: int) -> bool:
        # leaving the code inside exits[depth:] (break, continue, return, the end of a with block):
        # what each exit requires, innermost first, each in a block that the landing block around
        # its construct covers. A with block's file closes (its unwind action forgotten first); an
        # except clause restores the exception being handled before it, and unbinds its name; a
        # finally block runs as where its try statement is: in its loops, within the exits
        # outside it (where its own break or return goes). True if one of those took the way out
        # over (its own return, break, continue or raise), so that the caller's is not compiled
        here = self.handler
        cv = self.carried
        ended = False
        for i in range(len(self.exits) - 1, depth - 1, -1):
            if ended:
                break
            x = self.exits[i]
            self.handler = x.handler
            if self.blk.handler != x.handler:
                self.place(self.label())
            if x.kind == "with":
                if self.eh:
                    self.rt("pys_unwind_pop", "void", [])
                self.rt("pys_file_close", "void", [f"ptr {x.v}"])
            elif x.kind == "handler":
                self.rt("pys_exc_restore", "void", [f"ptr {x.v}"])
                self.unbind(x.name)
            elif x.entry != "":
                # a finally block compiled once (try_): it goes on here, by its index in conts; a
                # return's value is kept in a slot, as other ways out reach the code after it too
                sl = ""
                if cv.v.startswith("%"):
                    sl = self.alloca(cv.t, "")
                    self.emit(f"store {lt(cv.t)} {cv.v}, ptr {sl}")
                self.emit(f"store i64 {len(x.conts)}, ptr {x.sel}")
                x.conts.append(self.label())
                self.br(x.entry)
                self.place(x.conts[-1])
                self.narrowed = self.unnarrowed([x.body])  # (what the block may bind on the way)
                if sl != "":
                    cv = Val(self.ins(f"load {lt(cv.t)}, ptr {sl}"), cv.t)
            else:
                exits = self.exits
                loops = self.loops
                wdepth = self.wdepth
                excs = self.excs
                self.exits = exits[:i]
                self.loops = loops[: x.nloops]
                self.wdepth = wdepth[: x.nloops]
                self.excs = excs[: x.nexcs]
                t0 = self.term
                self.branch += 1
                self.stmts(x.body)
                self.branch -= 1
                ended = self.term and not t0
                self.exits = exits
                self.loops = loops
                self.wdepth = wdepth
                self.excs = excs
        self.handler = here
        self.carried = cv
        return ended

    def try_(self, n: Node) -> None:
        # try: B / except C1 as e: H1 / ... / else: L / finally: F. An exception raised in B goes to
        # the landing block of the except clauses (hE), one raised in a clause or L to that of F
        # (hF): from a call that may raise through the unwinder (an invoke), from a raise of this
        # function directly (see eh_ir). hE tests the clauses in order (exc.match) and throws again
        # what none catches; hF runs a copy of F and throws again. B and L, and each clause that
        # ends, go on to one copy of F; a break, continue or return out of the statement runs one
        # of its own (see leave), as CPython compiles F once for each way out. A clause whose name
        # may be read after it has a landing block of its own, which unbinds the name
        if n.s == "*":
            self.err("'except*' is not supported")
        hs: list[Node] = []
        orelse: list[Node] = []
        fin: list[Node] = []
        hasfin = False
        for k in n.kids[1:]:
            if k.kind == "except":
                k.kids[0] = self.clause_or(k.kids[0])
                hs.append(k)
            elif k.s == "else":
                orelse = k.kids
            else:
                fin = k.kids
                hasfin = True
        sets = [self.catches(h) for h in hs]
        self.line = n.line
        # what narrowed holds (see narrow_by) where an exception may come from: in a clause, what
        # held before the statement but for the names B binds; in F on the way out of an
        # exception, but for those that B, L and the clauses bind; after the statement, what holds
        # at the end of each way that goes on (ends)
        hst = self.unnarrowed([n.kids[0].kids])
        fst = self.unnarrowed([n.kids[0].kids, orelse] + [h.kids[1].kids for h in hs])
        ends: list[dict[str, bool]] = []
        # the try notes the depth of the unwind actions (pys_exc_begin runs those added since) and
        # the exception being handled, which every way out of its clauses restores
        mark = Val(self.rt("pys_try_mark", "i64", []), "int")
        old = self.rt("pys_exc_handled", "ptr", [])
        slot = self.alloca("exc", "")
        outer = self.handler
        he = self.label() if len(hs) > 0 else ""
        hf = self.label() if hasfin else ""
        done = self.label()
        tr = Try(self.label())
        tr.landing = he
        tr.final = hf
        tr.exit = done
        self.fn.tries.append(tr)
        self.branch += 1
        fx = Exit("finally", "", outer)
        if hasfin:
            fx.body = fin
            fx.nloops = len(self.loops)
            fx.nexcs = len(self.excs)
            if has_finally(fin):
                # a finally block that holds one: compiled once, after the rest of the statement,
                # where each way out stores its index and jumps (leave), else the copies of copies
                # would grow exponentially with the nesting (CPython's bytecode does)
                fx.entry = self.label()
                fx.sel = self.alloca("int", "")
            self.exits.append(fx)
        self.handler = he if he != "" else hf
        self.place(tr.body)
        self.stmts(n.kids[0].kids)
        self.handler = hf if hasfin else outer
        if len(orelse) > 0 and not (self.term and self.curfn.inst):
            tr.orelse = self.label()
            self.place(tr.orelse)
            self.stmts(orelse)
        live = not self.term  # (does any path go on to done)
        if live:
            ends.append(self.narrowed)
        self.br(done)
        if he != "":
            e = self.landing(he, slot, mark)
            nxt = ""
            for j in range(len(hs)):
                h = hs[j]
                self.line = h.line
                if h.s != "" and not self.modlevel and h.s in self.gdecl:
                    self.err(f"except ... as {h.s}, of the global '{h.s}', in a function is not supported: the end of the clause deletes the global, as del would")
                for c in h.kids[0].kids if h.kids[0].kind == "tuple" else [h.kids[0]] if h.kids[0].kind == "name" else h.kids[:0]:
                    if (c.chk or self.foreign(c.s)) and c.s in self.gflag and c.s in self.classes:
                        # a class whose class statement may not have run yet
                        self.guard(self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{c.s}.def')}, true"), self.unbound(c.s))
                if sets[j] != "":
                    l = self.label()
                    nxt = self.label()
                    self.cbr(self.exc_match(e, sets[j]), l, nxt)
                    self.place(l)
                self.narrowed = dict(hst)
                if h.s != "":
                    self.bind_as(h.s, e, self.as_type(h))
                x = Exit("handler", old, self.handler)
                x.name = h.s
                up = self.handler
                hu = ""
                if h.s != "" and self.unbinds(h.s) and up != "":
                    # an exception that leaves the clause unbinds its name too, where something may
                    # read it after (CPython deletes it in a finally block of its own): the clause
                    # has a landing block of its own, which unbinds the name and throws again (an
                    # imported module's code is in a landing block's region, see function)
                    hu = self.label()
                    self.handler = hu
                    self.place(self.label())
                self.exits.append(x)
                self.excs.append(e)
                self.stmts(h.kids[1].kids)
                self.excs.pop()
                self.exits.pop()
                if not self.term:
                    self.rt("pys_exc_restore", "void", [f"ptr {old}"])
                    self.unbind(h.s)
                    live = True
                    ends.append(self.narrowed)
                    self.br(done)
                self.handler = up
                if hu != "":
                    ue = self.landing(hu, slot, mark)
                    self.unbind(h.s)
                    self.throw(ue)
                if len(self.shadows) > 0 and self.shadows[-1][0] == h.s:
                    self.unshadow()
                if sets[j] == "":
                    nxt = ""
                    break  # (it catches everything: the clauses after it never run)
                self.place(nxt)
            if nxt != "":
                self.throw(e)
        if hasfin:
            self.exits.pop()
            self.handler = outer
            e = self.landing(hf, slot, mark)
            if fx.entry != "":
                # (the exception goes on after the finally block, from a slot of its own)
                sl = self.alloca("exc", "")
                self.emit(f"store ptr {e.v}, ptr {sl}")
                self.emit(f"store i64 {len(fx.conts)}, ptr {fx.sel}")
                fx.conts.append(self.label())
                self.br(fx.entry)
                self.place(fx.conts[-1])
                self.throw(Val(self.ins(f"load ptr, ptr {sl}"), "exc"))
            else:
                self.exits.append(Exit("handler", old, outer))  # (a break or return in F drops the exception)
                self.excs.append(e)
                self.narrowed = dict(fst)
                self.stmts(fin)
                self.excs.pop()
                self.exits.pop()
                if not self.term:
                    self.throw(e)
        self.handler = outer
        self.branch -= 1
        if live and fx.entry != "":
            self.place(done)
            self.emit(f"store i64 {len(fx.conts)}, ptr {fx.sel}")
            fx.conts.append(self.label())
            self.br(fx.entry)
        if fx.entry != "":
            # the finally block, once: the exception being handled is the one in flight on the way
            # out of an exception (a bare raise raises it: pys_reraise), else the one before the
            # statement, which a break or return in it restores; then each way out goes on
            self.place(fx.entry)
            self.exits.append(Exit("handler", old, outer))
            self.excs.append(Val("", "exc"))
            self.branch += 1
            self.narrowed = dict(fst)  # (each way in: fst holds on all of them)
            self.stmts(fin)
            self.branch -= 1
            self.excs.pop()
            self.exits.pop()
            disp = self.label()
            self.place(disp)
            ksel = self.ins(f"load i64, ptr {fx.sel}")
            for j in range(len(fx.conts) - 1):
                nx = self.label()
                self.cbr(self.ins(f"icmp eq i64 {ksel}, {j}"), fx.conts[j], nx)
                self.place(nx)
            self.br(fx.conts[-1])
            if live:
                self.place(fx.conts[-1])
        elif live:
            self.place(done)
            self.narrowed = meet(ends)
            self.stmts(fin)
        if not live:
            self.narrowed = {}  # (no code follows)

    def assert_fails(self, n: Node) -> None:
        # the AssertionError of assert statement n, whose test is false: with its message
        v = self.expr(n.kids[1], "") if len(n.kids) > 1 else Val(self.sconst(""), "str")
        if self.eh and v.t != "str":
            self.throw(self.exc_value("AssertionError", [v]))  # (repr(e) shows the repr of v)
        else:
            self.raise_("AssertionError", self.to_str(v).v)

    def unnarrowed(self, bodies: list[list[Node]]) -> dict[str, bool]:
        # a copy of narrowed without the names that the code of bodies binds or deletes: what
        # holds wherever an exception may come from in them
        out: dict[str, bool] = {}
        if len(self.narrowed) > 0:
            names: dict[str, bool] = {}
            for b in bodies:
                collect(b, names)
                deleted(b, names)
            for nm in self.narrowed:
                if nm not in names:
                    out[nm] = True
        return out

    def clause_or(self, t: Node) -> Node:
        # except A or B: the class that the clause's expression gives where each operand names an
        # exception class (a class is true: A for or, B for and), as CPython evaluates it
        todo = [t]
        while len(todo) > 0:
            c = todo.pop()
            if c.kind == "boolop":
                todo += c.kids
            elif not self.exc_classes(c):
                return t
        while t.kind == "boolop":
            t = t.kids[0] if t.s == "or" else t.kids[1]
        return t

    def catches(self, h: Node) -> str:
        # the classes except clause h catches: "" for every one (a bare except, BaseException), else
        # "\1A\1B\1" (pys_exc_in): the exception classes, builtin or the program's, deriving
        # from those it names (a class of the program by its qualified name, its ExcClass's)
        self.line = h.line
        return self.catch_set(h.kids[0])

    def exc_classes(self, t: Node) -> bool:
        # does t, isinstance's second argument, name exception classes only (a name, or a tuple of names)
        for c in t.kids if t.kind == "tuple" else [t]:
            if c.kind != "name" or self.bound(c.s) and not (c.s in self.classes and self.classes[c.s].exc != ""):
                return False
            if not is_excname(c.s) and c.s not in self.classes:
                return False
        return True

    def exc_isinst(self, v: Val, t: Node) -> Val:
        # isinstance(v, t) of an exception (or an exception object, which may be None), t naming
        # exception classes: decided by v's class where its type decides it, else by its ExcClass
        names = t.kids if t.kind == "tuple" else [t]
        if v.t != "exc":
            yes = False
            maybe = False
            for c in names:
                yes = yes or self.derives(v.t, c.s)
                maybe = maybe or self.derives(c.s, v.t)
            if yes or not maybe:
                return Val(self.ins(f"icmp ne ptr {v.v}, null") if yes and v.v not in self.nn else "true" if yes else "false", "bool")
        sets = self.catch_set(t)
        if v.t == "exc":
            return Val("true" if sets == "" else self.exc_match(v, sets), "bool")
        e0 = self.cur
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.isnull(v), l2, l1)
        self.place(l1)
        r = self.exc_match(Val(self.rt("pys_exc_user", "ptr", [f"ptr {v.v}"]), "exc"), sets)
        e1 = self.cur
        self.br(l2)
        self.place(l2)
        ph = Ins("phi", "bool", "")
        self.incoming(ph, "false", e0)
        self.incoming(ph, r, e1)
        return Val(self.phi(ph), "bool")

    def catch_set(self, t: Node) -> str:
        # the classes that t, the classes an except clause names, catches (catches)
        names: list[str] = []
        for c in t.kids if t.kind == "tuple" else [t] if t.kind != "omit" else t.kids:
            if c.kind == "attr" and (self.dotted(c) == "builtins." + c.s or self.dotted(c) == "os.error"):
                c = mk("name", "OSError" if c.s == "error" else c.s, c.line, [])  # (builtins.ValueError, os.error)
            if c.kind != "name" or c.s in self.ltype or c.s in self.gtypes or c.s in self.funcs or c.s in self.assigned:
                self.err("an except clause needs exception classes: a name, or a tuple of names")
            if c.s in self.unsupported:
                self.err(self.unsupported[c.s])
            if c.s in self.classes and self.classes[c.s].exc == "":
                self.err("catching classes that do not inherit from BaseException is not allowed")
            if c.s in self.classes:
                names.append(c.s)
                continue
            x = "OSError" if c.s == "IOError" or c.s == "EnvironmentError" else c.s
            if x not in EXCBASES:
                self.err(f"name '{short(c.s)}' is not defined" if c.s not in PYBUILTINS else "catching classes that do not inherit from BaseException is not allowed")
            names.append(x)
        if t.kind == "tuple" and len(names) == 0:
            return "\x01\x01"  # (an empty tuple catches nothing)
        if len(names) == 0 or "BaseException" in names:
            return ""
        out: list[str] = []
        for k in EXCBASES:
            for b in names:
                if b in EXCBASES and exc_derives(k, b):
                    out.append(k)
                    break
        for k in self.classes:
            for b in names:
                if self.classes[k].exc != "" and self.derives(k, b):
                    out.append(k)
                    break
        return "\x01" + "\x01".join(out) + "\x01"

    def as_type(self, h: Node) -> str:
        # the type of the name except clause h binds: the nearest exception class of the program
        # that every class it names derives from (the name is the exception's object), else exc
        t = h.kids[0]
        cs = t.kids if t.kind == "tuple" else [t]
        c = cs[0].s if t.kind != "omit" and len(cs) > 0 else ""
        while c in self.classes:
            ok = True
            for x in cs:
                ok = ok and self.derives(x.s, c)
            if ok:
                return c
            c = self.classes[c].base
        return "exc"

    def bind_as(self, name: str, e: Val, t: str) -> None:
        # except ... as name: name is exception e, or its object (of class t of the program). Where
        # name has another type, or no type yet but another binding in its scope (which may give it
        # one), it gets a variable of its own for the clause (the end of which unbinds both, see
        # unbind, as CPython deletes the name). Not a module's global that a function reads, which
        # would not see the exception
        v = e if t == "exc" else Val(self.rt("pys_exc_obj", "ptr", [f"ptr {e.v}"]), t)
        self.nn[v.v] = True
        had = self.ltype[name] if name in self.ltype else self.gtypes[name] if self.is_global(name) and name in self.gtypes else ""
        node = self.curfn.node
        if (had != "" and had != t) or (had == "" and binds_other(node.kids if node.kind == "block" else node.kids[2].kids, name)):
            f = self.global_reader(name) if self.modlevel else ""
            if f != "":
                self.err(f"except ... as {short(name)} is not supported here: the module's global '{short(name)}' has another type, so the clause binds a variable of its own, which {f}() would not see (use another name)")
            self.shadows.append([name, self.ltype.get(name, ""), self.lreg.get(name, ""), self.lflag.get(name, "")])
            if name in self.lflag:
                del self.lflag[name]
            self.alloca(t, name)
        self.store_name(name, v)

    def global_reader(self, name: str) -> str:
        # a function or method of the program that reads module global name, or ""
        fs = list(self.funcs.values())
        for ci in self.classes.values():
            fs += list(ci.methods.values())
        for f in fs:
            if f.mod != owner(name) or f.node.kind != "def" or name in f.params:
                continue
            body = f.node.kids[2].kids
            decl: dict[str, bool] = {}
            globals_in(body, decl)
            if name in decl or not (binds_other(body, name) or binds_as(body, name)):
                for st in body:
                    if reads(st, name):
                        return short(f.name)
        return ""

    def unbinds(self, name: str) -> bool:
        # does unbind(name) clear an "is assigned" flag (a read that may follow tests it)
        if name in self.ltype and name in self.lflag or name not in self.ltype and name in self.gflag:
            return True
        for s in self.shadows:
            if s[0] == name and (s[3] != "" or (s[1] == "" and name in self.gflag)):
                return True
        return False

    def unshadow(self) -> None:
        # the end of the except clause whose name has a variable of its own (bind_as): the name is the other again
        s = self.shadows.pop()
        if s[1] == "":
            del self.ltype[s[0]]
            del self.lreg[s[0]]
        else:
            self.ltype[s[0]] = s[1]
            self.lreg[s[0]] = s[2]
        if s[3] != "":
            self.lflag[s[0]] = s[3]
        elif s[0] in self.lflag:
            del self.lflag[s[0]]

    def landing(self, l: str, slot: str, mark: Val) -> Val:
        # landing block l of a try statement, where an exception comes through the unwinder: its
        # landing op stores the exception in slot, as a raise in this function that goes there does
        # (see eh_ir), and both go on to the code after it, which takes the exception up: the
        # unwind actions since the try's mark run, and it becomes the exception being handled
        j = self.label()
        self.place(l)
        i = Ins("landing", "exc", "")
        i.a = [Val(slot, "%addr")]
        i.b = [j]
        self.put(i, 2)
        self.term = True
        self.place(j)
        x = self.ins(f"load ptr, ptr {slot}")
        return Val(self.rt("pys_exc_begin", "ptr", [f"ptr {x}", f"i64 {mark.v}"]), "exc")

    def exc_match(self, e: Val, names: str) -> str:
        # does exception e belong to the classes names ("\1A\1B\1")
        i = Ins("exc.match", "bool", "")
        i.a = [e, Val(self.sconst(names), "str")]
        self.runtime("pys_exc_in")
        self.put(i, 2)
        return f"%t{i.r[1]}"

    def unbind(self, name: str) -> None:
        # the end of except ... as name: name is unbound, as after del name (but nothing is read),
        # and so are the variables of that name around it (bind_as)
        if name in self.ltype and name in self.lflag:
            self.emit(f"store i1 false, ptr {self.lflag[name]}")
        elif name != "" and name not in self.ltype and name in self.gflag:
            self.emit(f"store i1 false, ptr @g.{name}.def")
        for s in self.shadows:
            if s[0] == name and s[3] != "":
                self.emit(f"store i1 false, ptr {s[3]}")
            elif s[0] == name and s[1] == "" and name in self.gflag:
                self.emit(f"store i1 false, ptr @g.{name}.def")

    def exc_args(self, e: Node) -> list[Node]:
        # the arguments of raise E / raise E(args), checking that E is a builtin exception
        if e.kind == "call" and e.kids[0].kind == "name":
            name = e.kids[0].s
            args = e.kids[1:]
        elif e.kind == "name":
            name = e.s
            args = []
        else:
            self.err("raise needs an exception class or a call of one, such as raise ValueError(msg)")
        if name in self.ltype or name in self.gtypes or name in self.funcs:
            self.err("exceptions must derive from BaseException: raise needs an exception class or a call of one")
        if name not in EXCEPTIONS:
            self.err(f"name '{name}' is not defined")
        if EXCEPTIONS[name] == "-":
            self.err(f"raising {name} is not supported")
        self.exc_kw(name, args, name + "()")
        npos = 0
        for a in args:
            npos += 1 if a.kind != "kw" else 0
        oe = exc_base_of(name, "OSError")
        if npos > 1 and EXCEPTIONS[name] != "" and not (oe and npos <= 3):
            self.err(f"{name}() with more than {'three arguments' if oe else 'one argument'} is not supported")
        return args

    def exc_kw(self, c: str, args: list[Node], what: str) -> None:
        # the keyword arguments of a call of builtin exception class c (or of its __init__, what):
        # those CPython's takes (an ImportError's name and path, ...), which set attributes that
        # only CPython reads (exc_vals evaluates and drops them)
        ok = (EXCKW["ImportError"] if exc_base_of(c, "ImportError") else EXCKW["AttributeError"] if exc_base_of(c, "AttributeError")
              else EXCKW["NameError"] if exc_base_of(c, "NameError") else "").split()
        for a in args:
            if a.kind == "kw" and len(ok) == 0:
                self.err(f"{what} takes no keyword arguments")
            if a.kind == "kw" and a.s not in ok:
                self.err(f"{what} got an unexpected keyword argument '{a.s}'")

    def exc_vals(self, args: list[Node]) -> list[Val]:
        # the positional arguments of a call of a builtin exception class, its keyword arguments
        # evaluated in order too (exc_kw)
        vals: list[Val] = []
        for a in args:
            if a.kind == "kw":
                self.expr(a.kids[0], "")
            else:
                vals.append(self.expr(a, ""))
        return vals

    def exc_class(self, e: Node) -> str:
        # the class that e, the exception of a raise statement, names or calls: a builtin exception
        # class (EXCEPTIONS) or a class of the program; "" for any other expression (a variable,
        # a call of a function), whose value is the exception
        c = e.kids[0] if e.kind == "call" else e
        if c.kind != "name" or c.s in self.funcs or c.s in self.ltype or c.s in self.gtypes:
            return ""
        return c.s if c.s in self.classes or c.s in EXCEPTIONS else ""

    def cause(self, c: Node) -> None:
        # raise ... from c: c is evaluated and checked (an exception class, a call of one, an
        # exception or None: else CPython's TypeError is raised instead), and otherwise ignored:
        # only a traceback would show it
        if c.kind == "None":
            return
        k = self.exc_class(c)
        if k == "" or k in self.classes:
            v = self.exc_value_of(c, k)
            if v.t != "exc" and v.t != "None" and not (v.t in self.classes and self.classes[v.t].exc != ""):
                self.raise_("TypeError", self.sconst("exception causes must derive from BaseException"))
                self.place(self.label())  # (what follows, the raise itself, is never reached)
            return
        self.exc_vals(self.exc_args(c))

    def exc_value_of(self, e: Node, k: str) -> Val:
        # the value of e, the exception of a raise statement, unless it is a builtin exception class
        # or a call of one: a class of the program k (or a call of it) makes an object of it
        if k == "":
            return self.expr(e, "")
        if self.classes[k].exc == "":
            self.err(f"'{short(k)}' is not an exception class: exceptions must derive from BaseException")
        return self.exc_object(k, e.kids[1:] if e.kind == "call" else [])

    def raise_stmt(self, n: Node) -> None:
        # raise E(args) [from C]: CPython's last traceback line, "E: str(arg)" (KeyError: repr(arg);
        # several arguments: their tuple's repr); SystemExit ends the program like sys.exit. In a
        # program that has a try, it throws the exception CPython makes (exc_value), which the
        # program ends with as before if nothing catches it
        if len(n.kids) == 0:
            # a bare raise: the exception the except clause around it handles, or else the one
            # being handled where it runs (in a function an except clause calls)
            if len(self.excs) > 0 and self.excs[-1].v != "":
                self.throw(self.excs[-1])
            elif self.eh:
                self.rt("pys_reraise", "void", [])
                self.unreachable()
            else:
                self.raise_("RuntimeError", self.sconst("No active exception to reraise"))
            return
        e = n.kids[0]
        k = self.exc_class(e)
        if k == "" or k in self.classes:
            v = self.exc_value_of(e, k)
            if v.t in self.classes and self.classes[v.t].exc != "":
                v = self.exc_of(v)
            if v.t != "exc":
                self.err("exceptions must derive from BaseException: raise needs an exception class or a call of one")
            if len(n.kids) > 1:
                self.cause(n.kids[1])
            self.throw(v)
            return
        name = e.kids[0].s if e.kind == "call" else e.s
        vals = self.exc_vals(self.exc_args(e))
        if len(n.kids) > 1:
            self.cause(n.kids[1])
        if n.s == "init":
            # a module's raise of ImportError at its top level (Loader.init_raise()): under an optional
            # import (a "guard" in a uimport) the module returns, not imported, so that the importer's
            # handler runs and a later import runs its code again
            g = self.curfn.ll + ".guard"
            self.global_var(g, "i1")
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.ins(f"load i1, ptr {g}"), l1, l2)
            self.place(l1)
            self.emit(f"store i1 false, ptr {self.curfn.ll}.done")
            self.ret_(Val("null", "None"))
            self.place(l2)
        if name == "SystemExit":
            self.exit_(vals)
            return
        if self.eh:
            self.throw(self.exc_value("OSError" if name == "IOError" or name == "EnvironmentError" else name, vals))
            return
        if name == "SyntaxError" or name == "IndentationError" or name == "TabError":
            # CPython's traceback takes str(e), which is str(msg), then prints "E: " and str(msg or
            # "<no detail available>"), the ": " even before an empty str(msg), which pys_raise leaves
            # out: the raise op's kind operand is then that whole line, and its message empty
            if len(vals) == 1:
                self.to_str(vals[0])
                l1 = self.label()
                l2 = self.label()
                self.cbr(self.truth(vals[0]), l1, l2)
                self.place(l1)
                line = self.rt("pys_str_add", "ptr", [f"ptr {self.sconst(name + ': ')}", f"ptr {self.to_str(vals[0]).v}"])
                self.raise_(name, self.sconst(""), line)
                self.place(l2)
            self.raise_(name, self.sconst("<no detail available>"))
            return
        name = "OSError" if name == "IOError" or name == "EnvironmentError" else name
        if len(vals) > 1 and exc_base_of(name, "OSError"):
            oe = self.os_error(name, vals)
            self.raise_(name, oe[1], oe[0])
            return
        if len(vals) > 1:
            msg = self.repr(self.tuple_(vals)).v
        elif len(vals) == 1:
            msg = (self.repr(vals[0]) if name == "KeyError" else self.to_str(vals[0])).v
        else:
            msg = self.sconst("")
        self.raise_(name, msg)

    def os_error(self, name: str, vals: list[Val]) -> list[str]:
        # OSError(errno, strerror[, filename]) of builtin class name, as CPython's makes it: str(e)
        # "[Errno n] strerror" (then ": " and repr(filename), unless it is None), args (errno,
        # strerror) (and None), of the subclass the errno names where name is OSError itself.
        # Gives its kind, str(e) and what repr(e) shows between its parentheses
        no = vals[0]
        kind = self.sconst(name) if name in EXCBASES else ""  # (an exception class of the program's is its own)
        if name == "OSError" and (no.t == "int" or no.t == "bool"):
            kind = self.rt("pys_exc_errcls", "ptr", [f"i64 {self.as_int(no).v}"])
        msg = self.cat(Val(self.sconst("[Errno "), "str"), self.to_str(no))
        msg = self.cat(self.cat(msg, Val(self.sconst("] "), "str")), self.to_str(vals[1]))
        args = self.cat(self.cat(self.repr(no), Val(self.sconst(", "), "str")), self.repr(vals[1]))
        if len(vals) == 3 and vals[2].t == "None":
            args = self.cat(args, Val(self.sconst(", None"), "str"))
        elif len(vals) == 3:
            msg = self.cat(self.cat(msg, Val(self.sconst(": "), "str")), self.repr(vals[2]))
        return [kind, msg.v, args.v]

    def exc_value(self, name: str, vals: list[Val]) -> Val:
        # the exception name(*vals) of a builtin class name (pys_exc_new): str(e), and what repr(e)
        # shows between its parentheses (null: the repr of str(e), as for one str argument)
        args = "null"
        detail = ""
        if name == "SyntaxError" or name == "IndentationError" or name == "TabError":
            # str(e) is str(msg) ("None" without), but its traceback shows "E: " and str(msg or
            # "<no detail available>")
            msg = self.to_str(vals[0]).v if len(vals) == 1 else self.sconst("None")
            no = Val(self.sconst("<no detail available>"), "str")
            detail = self.select(self.truth(vals[0]), Val(msg, "str"), no) if len(vals) == 1 else no.v
            if len(vals) == 0:
                args = self.sconst("")
            elif vals[0].t != "str":
                args = self.repr(vals[0]).v
        elif len(vals) > 1 and exc_base_of(name, "OSError"):
            oe = self.os_error(name, vals)
            return Val(self.rt("pys_exc_new", "ptr", [f"ptr {oe[0]}", f"ptr {oe[1]}", f"ptr {oe[2]}"]), "exc")
        elif len(vals) > 1:
            msg = self.repr(self.tuple_(vals)).v
            args = self.rt("pys_str_slice", "ptr", [f"ptr {msg}", "i64 1", "i64 -1"])
        elif len(vals) == 1:
            msg = (self.repr(vals[0]) if name == "KeyError" else self.to_str(vals[0])).v
            if vals[0].t != "str" and name != "KeyError":
                args = self.repr(vals[0]).v  # (a KeyError's message is its argument's repr already)
        else:
            msg = self.sconst("")
        e = self.rt("pys_exc_new", "ptr", [f"ptr {self.sconst(name)}", f"ptr {msg}", f"ptr {args}"])
        if detail != "":
            e = self.rt("pys_exc_detail", "ptr", [f"ptr {e}", f"ptr {detail}"])
        return Val(e, "exc")

    def exit_(self, vals: list[Val]) -> None:
        # sys.exit(code) and raise SystemExit(code): None is status 0, an int is the status, and
        # anything else is printed to stderr with status 1. In a program that has a try, a code
        # whose str() or repr() the runtime would not show as CPython's (None, a bool, several
        # arguments, anything but an int or a str) is thrown as the exception exit_value makes
        if self.eh and (len(vals) != 1 or (vals[0].t != "int" and vals[0].t != "str" and vals[0].t not in self.classes)):
            self.throw(self.exit_value(vals))
            return
        if len(vals) > 1:
            self.rt("pys_exit_msg", "void", [f"ptr {self.repr(self.tuple_(vals)).v}"])
        elif len(vals) == 0 or vals[0].t == "None":
            self.rt("pys_exit", "void", ["i64 0"])
        elif vals[0].t == "int" or vals[0].t == "bool":
            self.rt("pys_exit", "void", [f"i64 {self.as_int(vals[0]).v}"])
        else:
            if vals[0].t in self.classes or is_opt(vals[0].t):
                # an object that is None at run time is status 0 too
                l1 = self.label()
                l2 = self.label()
                self.cbr(self.isnull(vals[0]), l1, l2)
                self.place(l1)
                if self.eh:
                    self.throw(self.no_code())
                else:
                    self.rt("pys_exit", "void", ["i64 0"])
                    self.unreachable()
                self.place(l2)
            if is_sopt(vals[0].t):
                self.exit_([self.deref(vals[0])])  # (an int is the status)
                return
            if self.eh and vals[0].t != "str":
                self.throw(self.exc_value("SystemExit", vals))
                return
            self.rt("pys_exit_msg", "void", [f"ptr {self.to_str(vals[0]).v}"])
        self.unreachable()

    def no_code(self) -> Val:
        # SystemExit(None): status 0, str(e) ""
        e = self.sconst("")
        return Val(self.rt("pys_exc_exit", "ptr", ["i64 0", f"ptr {e}", f"ptr {e}"]), "exc")

    def exit_value(self, vals: list[Val]) -> Val:
        # SystemExit(*vals): an int or bool code is the status the program ends with if nothing
        # catches it, None (or none) status 0; anything else is shown, with status 1. (sys.exit(None)
        # is SystemExit(), but SystemExit(None) shows its None: str(e) "None")
        if len(vals) == 0:
            return self.no_code()
        if len(vals) == 1 and (vals[0].t == "int" or vals[0].t == "bool" or vals[0].t == "None"):
            s = self.to_str(vals[0]).v
            return Val(self.rt("pys_exc_exit", "ptr", [f"i64 {self.as_int(vals[0]).v if vals[0].t != 'None' else '0'}", f"ptr {s}", f"ptr {s}"]), "exc")
        return self.exc_value("SystemExit", vals)

    def exc_object(self, c: str, args: list[Node]) -> Val:
        # c(args), c an exception class: an object made as BaseException.__new__ makes it (its
        # ExcClass, and the args kept as str(e) and repr(e) show them, see exc_keep), with the
        # class-body defaults, then given to the __init__ of c or of the nearest base that has
        # one; without one, the class takes any positional arguments
        ci = self.classes[c]
        if ci.bad != "":
            self.err(ci.bad)
        line = self.line
        init = ci.methods["__init__"] if "__init__" in ci.methods else None
        vals: list[Val] = []
        kws: list[Node] = []
        for a in args:
            if a.kind == "kw" and init is None:
                # (the keywords its builtin base's __init__ takes, ImportError's name and path, ...)
                self.exc_kw(ci.exc, [a], f"{short(c)}()")
                self.expr(a.kids[0], "")
            elif a.kind == "kw":
                kws.append(a)
            else:
                j = len(vals) + 1
                vals.append(self.expr(a, init.ptypes[j] if init is not None and j < init.npos else ""))
        if init is not None and len(vals) >= init.npos:
            self.err(f"{short(init.cls)}.__init__() takes {init.npos} positional argument{'s' if init.npos > 1 else ''} but {len(vals) + 1} were given")
        size = f"ptrtoint (ptr getelementptr (%C.{c}, ptr null, i32 1) to i64)"
        o = Val(self.rt("pys_alloc", "ptr", [f"i64 {size}"]), c)
        self.nn[o.v] = True
        self.xcls[c] = True
        self.setfield(o, self.field(o, " cls"), " cls", Val(f"@x.{c}", "str"))
        # (with an __init__ of the program, an OSError's args are left empty, and a SystemExit's
        # code None, until its super().__init__() sets them, as OSError.__new__ and SystemExit.__init__ do)
        self.exc_keep(o, vals if init is None or not self.derives(c, "OSError") else vals[:0], init is None)
        for fl in ci.fields:
            if fl in ci.fdefault and c + "." + fl not in self.cvars:  # (a class variable is read from the class, see getfield)
                h = self.default_home(ci, fl)
                t = ci.ftypes[fl]
                if not is_const(ci.fdefault[fl]):
                    self.class_default(h, fl)
                v = Val(self.ins(f"load {lt(t)}, ptr {h.fglob[fl]}"), t) if fl in h.fglob else self.coerce(self.expr(ci.fdefault[fl], t), t)
                self.setfield(o, self.field(o, fl), fl, v)
        self.line = line
        if init is not None:
            self.call_fn(init, [o] + vals, kws)
        return o

    def exc_keep(self, o: Val, vals: list[Val], coded: bool = True) -> None:
        # what exception object o keeps of its args vals (BaseException.__new__, and its __init__
        # through super().__init__): str(e) (a KeyError's: the repr of its one argument) and the
        # text between repr(e)'s parentheses; a SystemExit's status and whether its code is one
        # (unless coded is False: its code is None)
        c = o.t
        if len(vals) > 3 and self.derives(c, "OSError"):
            self.err(f"{short(c)}() with more than three arguments is not supported")
        if len(vals) > 1 and self.derives(c, "OSError"):
            oe = self.os_error(c, vals)  # ("[Errno n] text")
            sv = oe[1]
            av = oe[2]
        elif len(vals) == 0:
            sv = self.sconst("")
            av = sv
        elif len(vals) == 1:
            av = self.repr(vals[0]).v
            sv = av if self.derives(c, "KeyError") else self.to_str(vals[0]).v
        else:
            sv = self.repr(self.tuple_(vals)).v
            av = self.rt("pys_str_slice", "ptr", [f"ptr {sv}", "i64 1", "i64 -1"])
        self.setfield(o, self.field(o, " str"), " str", Val(sv, "str"))
        self.setfield(o, self.field(o, " args"), " args", Val(av, "str"))
        if self.derives(c, "SystemExit"):
            code = "0"
            hc = "true" if len(vals) == 0 or not coded else "false"
            if len(vals) == 1 and coded:
                t = vals[0].t
                if t == "int" or t == "bool":
                    code = self.as_int(vals[0]).v
                hc = "true" if t == "int" or t == "bool" or t == "None" else self.isnull(vals[0]) if t in self.classes else "false"
            self.setfield(o, self.field(o, " code"), " code", Val(code, "int"))
            self.setfield(o, self.field(o, " hc"), " hc", Val(hc, "bool"))

    def exc_of(self, v: Val) -> Val:
        # the exception that raises exception object v
        self.notnone(v, "TypeError: exceptions must derive from BaseException")
        return Val(self.rt("pys_exc_user", "ptr", [f"ptr {v.v}"]), "exc")

    def exc_brepr(self, o: Val) -> Val:
        # BaseException.__repr__ of exception object o: the name of its class, and its args
        a = self.getfield(o, self.field(o, " args"), " args")
        return Val(self.rt("pys_exc_brepr", "ptr", [f"ptr {o.v}", f"ptr {a.v}"]), "str")

    def super_call(self, sc: Node, m: str, args: list[Node]) -> Val:
        # super().m(args) in a method of an exception class: the base's method m, or what
        # BaseException's __init__ (keep the args), __str__ and __repr__ do
        cls = self.curfn.cls
        me0 = self.curfn.params[0] if cls != "" else ""
        # (super(C, self), in a method of class C, is super())
        same = len(sc.kids) == 3 and sc.kids[1].kind == "name" and sc.kids[1].s == shown(cls) and sc.kids[2].kind == "name" and sc.kids[2].s == me0
        if (len(sc.kids) > 1 and not same) or cls == "" or self.classes[cls].exc == "":
            self.err("super() is only supported without arguments, in the methods of exception classes (super(C, self) in a method of C is super())")
        me = self.expr(mk("name", self.curfn.params[0], sc.line, []), "")
        b = self.classes[cls].base
        if b in self.classes and m in self.classes[b].methods:
            return self.call_fn(self.classes[b].methods[m], [me], args)
        if m == "__init__":
            self.exc_kw(b, args, f"{short(b)}.__init__()")
            vals = self.exc_vals(args)
            self.exc_keep(me, vals)
            return Val("null", "None")
        if (m == "__str__" or m == "__repr__") and len(args) == 0:
            return self.getfield(me, self.field(me, " str"), " str") if m == "__str__" else self.exc_brepr(me)
        self.err(f"super().{m}() is not supported: only __init__, __str__, __repr__ and the methods of a base class of the program")
        return me

    def exc_helpers(self, c: str) -> None:
        # the ExcClass of exception class c (runtime.c's exceptions): its name, which an except
        # clause matches, the name an uncaught exception's line shows, and its str, repr and (for
        # a SystemExit) exit functions: those of the class, or BaseException's
        ci = self.classes[c]
        line = ci.node.line
        me = mk("name", "self", line, [])
        noann = mk("noann", "", line, [])
        bodies: list[list[Node]] = []
        for m in ["__str__", "__repr__"]:
            if m in ci.methods:
                r = mk("call", "", line, [mk("attr", m, line, [me])])
            elif m == "__str__":
                r = mk("attr", " str", line, [me])
            else:
                r = mk("call", "", line, [mk("name", "__pys_exc_repr", line, []), me])
            bodies.append([mk("return", "", line, [r])])
        if self.derives(c, "SystemExit"):
            # the SystemExit that ends the program as this one does (exit_value)
            sysexit = mk("name", "SystemExit", line, [])
            code = mk("block", "", line, [mk("return", "", line, [mk("call", "", line, [sysexit, mk("attr", " code", line, [me])])])])
            bodies.append([mk("if", "", line, [mk("attr", " hc", line, [me]), code, mk("block", "", line, [])]),
                           mk("return", "", line, [mk("call", "", line, [sysexit, mk("attr", " str", line, [me])])])])
        names = ["str", "repr", "exit"]
        for i in range(len(bodies)):
            f = FnInfo(names[i], f"@x.{names[i]}.{c}", ci.node, c)
            f.params = ["self"]
            f.ptypes = [c]
            f.defaults = [noann]
            f.dglob = [""]
            f.ret = "exc" if i == 2 else "str"
            self.function(f, bodies[i])
        ex = f"ptr @x.exit.{c}" if len(bodies) == 3 else "ptr null"
        self.consts.append(f"@x.{c} = private constant {{ptr, ptr, ptr, ptr, ptr}} {{ptr {self.sconst(c)}, ptr {self.sconst(shown(c))}, ptr @x.str.{c}, ptr @x.repr.{c}, {ex}}}")

    def throw(self, e: Val) -> None:
        # raise exception e: to the landing block around, or out of the function (pys_throw)
        i = Ins("throw", "", "")
        i.a = [e]
        self.runtime("pys_throw")
        self.add(i)
        self.term = True

    def raise_(self, name: str, msg: str, kind: str = "") -> None:
        # raise exception name: the error line is "<kind>: <msg>", where kind is name unless given
        i = Ins("raise", "", name)
        i.a = [Val(kind if kind != "" else self.sconst(name), "str"), Val(msg, "str")]
        self.runtime("pys_raise")
        self.add(i)
        self.term = True

    def stmt(self, n: Node) -> None:
        self.line = n.line
        k = n.kind
        if k == "expr":
            if n.kids[0].kind != "str" and n.kids[0].kind != "ellipsis":
                self.expr(n.kids[0], "")  # (a string or ... alone does nothing)
        elif k == "assign":
            val = n.kids[-1]
            t0 = n.kids[0]
            self.copying = n.s == "from" and self.foreign(val.s)
            if len(n.kids) == 2 and t0.kind == "name" and empty_display(val) and self.ltype.get(t0.s, "") == NONEVAR and not self.is_global(t0.s):
                self.err(f"cannot infer the type of '{t0.s}' from None and an empty {val.kind}; annotate it ({t0.s}: {val.kind}[{'T' if val.kind == 'list' else 'K, V'}] | None = None)")
            if len(n.kids) == 2 and t0.kind == "name" and (val.kind == "list" or val.kind == "dict") and len(val.kids) == 0 and (self.target_type(t0) == "" or "?" in self.target_type(t0)):
                self.assign(t0, self.empty(val.kind, t0.s))
            elif len(n.kids) == 2 and t0.kind == "name" and val.kind == "name" and self.is_global(t0.s) and (t0.s not in self.gtypes or self.twin_of.get(t0.s, "-") == self.twin_of.get(val.s, "")) and t0.s not in self.noneglobals and not self.copying and self.globread(val.s) and "?" in self.gtypes.get(val.s, ""):
                # X = Y between module globals, Y an empty container without a type yet (from m
                # import Y copies it so): they are twins, which the first use of either types
                # (ahead may have made them so already)
                self.allowq = True
                self.assign(t0, self.read(val))
                self.allowq = False
                self.twin(t0.s, val.s)
            elif len(n.kids) == 2 and t0.kind == "tuple" and (val.kind == "tuple" or val.kind == "list") and len(t0.kids) == len(val.kids):
                vs: list[Val] = []
                for i in range(len(val.kids)):
                    vs.append(self.expr(val.kids[i], self.target_type(t0.kids[i])))
                for i in range(len(vs)):
                    self.assign(t0.kids[i], vs[i])
            else:
                if t0.kind == "index" and t0.kids[0].kind == "name" and "?" in self.rtype(t0.kids[0].s) and empty_display(val):
                    self.no_type(t0.kids[0].s)  # (d[k] = [] shows nothing of what d holds)
                v = self.expr(val, self.target_type(t0))
                for i in range(len(n.kids) - 1):
                    self.assign(n.kids[i], v)
            self.copying = False
        elif k == "annassign":
            if n.s != "" and self.ann_problem(n.kids[1], False) != "":
                self.err(n.s)  # (the declaration of a local that only dropped code binds: Loader.dropped_locals())
            t = self.vtype(n.kids[1])
            if n.kids[0].kind == "name":
                self.declare(n.kids[0].s, t)
            if len(n.kids) == 3:
                v = self.expr(n.kids[2], t)
                # (x: T | None = <a T> knows x holds a T, see narrowed)
                self.assign(n.kids[0], v if n.kids[0].kind == "name" and is_opt(t) and self.widens(v.t, t) else self.coerce(v, t))
        elif k == "augassign":
            self.augassign(n)
        elif k == "if":
            st = self.static(n.kids[0])
            if st >= 0:
                # the static types decide the test (isinstance(x, str), x is None): only the branch
                # that runs is compiled
                self.stmts(n.kids[1].kids if st == 1 else n.kids[2].kids)
                return
            c = self.cond(n.kids[0])
            l1 = self.label()
            l2 = self.label()
            l3 = self.label()
            self.cbr(c, l1, l2)
            self.branch += 1
            self.place(l1)
            pre = self.narrow_by(n.kids[0], True)
            self.stmts(n.kids[1].kids)
            yes = self.narrowed
            ygo = not self.term
            self.br(l3)
            self.place(l2)
            self.narrowed = pre
            self.narrow_by(n.kids[0], False)
            self.stmts(n.kids[2].kids)
            ngo = not self.term
            self.branch -= 1
            self.place(l3)
            # after the if: what holds at the end of each branch that goes on
            if ygo and not ngo:
                self.narrowed = yes
            elif ygo and ngo and len(yes) + len(self.narrowed) > 0:
                no = self.narrowed
                self.narrowed = {}
                for both in yes:
                    if both in no:
                        self.narrowed[both] = True
        elif k == "while" and self.static(n.kids[0]) == 0:
            # a loop whose test is false from the start (while x: with x None): only its else block runs
            if n.kids[-1].s == "else":
                self.stmts(n.kids[-1].kids)
        elif (k == "while" or k == "for") and n.kids[-1].s == "else":
            # for/while ... else: break leaves the loop past the else block
            ek = self.elsekids
            eb = self.elsebrk
            self.elsekids = n.kids[2 if k == "for" else 1].kids
            self.elsebrk = self.label()
            self.elsebrks = []  # (a loop over () has no body to compile)
            lb = self.elsebrk
            if k == "for":
                self.for_(n, [])
            else:
                self.while_(n)
            self.elsekids = ek
            self.elsebrk = eb
            brks = self.elsebrks
            self.branch += 1
            self.stmts(n.kids[-1].kids)
            self.branch -= 1
            # after it: what holds at the end of the else block (if it goes on) and at each break
            if not self.term:
                brks.append(self.narrowed)
            if len(brks) > 0:
                self.narrowed = meet(brks)
            self.place(lb)
        elif k == "while":
            self.while_(n)
        elif k == "for":
            self.for_(n, [])
        elif k == "return":
            if self.modlevel:
                self.err("'return' outside function")
            if self.ret == "":
                # the first return of a template's function with a value decides what the function
                # returns; a return of None before it is lowered from what that decided
                v = self.retval(n.kids[0], "") if len(n.kids) > 0 else Val("null", "None")
                if v.t != "None":
                    t = v.t
                    if self.optional(t) != t and self.optional(t) != "" and self.returned_none():
                        t = self.optional(t)  # after a return of None: T | None (before it calls itself)
                    self.ret = t
                    self.curfn.ret = t
                    v = self.coerce(v, t)
                self.carried = v
                ended = self.leave(0)
                v = self.carried
                self.carried = Val("", "")
                if ended:
                    pass  # (a finally block returned instead)
                elif v.t == "None":
                    self.add(Ins("ret.none", "", ""))
                else:
                    self.ret_(v)
            elif len(n.kids) == 0 or (self.ret == "None" and n.kids[0].kind == "None"):
                if self.ret != "None" and self.curfn.infer and self.optional(self.ret) != self.ret and self.optional(self.ret) != "":
                    self.reopt(self.optional(self.ret))  # a template's function returns T, and None: T | None
                if self.ret != "None" and not (self.curfn.infer and self.ret in self.classes) and not is_opt(self.ret):
                    self.err(self.nonemix(self.curfn, self.ret) if self.curfn.infer else f"missing return value of type {self.ret}")
                if not self.leave(0):
                    self.ret_(Val("null", self.ret))
            elif self.ret == "None":
                # return f() where f returns None
                v = self.expr(n.kids[0], "")
                if v.t != "None" and self.curfn.infer:
                    self.err(self.nonemix(self.curfn, v.t))
                if v.t != "None":
                    self.err(f"returning {v.t} from a function declared to return None" if self.retann else "returning a value from a function without a return annotation")
                if not self.leave(0):
                    self.ret_(Val("null", "None"))
            else:
                v = self.iter_ret(n.kids[0]) if self.curfn.iters else self.retval(n.kids[0], self.ret)
                if "?" in self.ret and "?" not in v.t and same_kind(v.t, self.ret):
                    self.adopt(v.t)  # (it returned an empty container without a type before)
                j = self.join(self.ret, v.t) if self.curfn.infer and v.t != self.ret else self.ret
                if j != self.ret and j != "" and is_opt(j):
                    self.reopt(j)  # a template's function returns T and None (or T | None): T | None
                if self.curfn.infer and v.t != self.ret and not (v.t == "None" and self.ret in self.classes) and not self.widens(v.t, self.ret) and not self.boxes(v.t, self.ret):
                    if v.t == "None":
                        self.err(self.nonemix(self.curfn, self.ret))
                    self.err(f"{short(self.curfn.name)}() returns both {typestr(self.ret)} and {typestr(v.t)} (each function has one return type)")
                v = self.coerce(v, self.ret, f"the value {short(self.curfn.name)}() returns ({typestr(self.ret)})" if is_opt(v.t) else "")
                self.carried = v  # (the value first: a finally block runs after it is computed)
                ended = self.leave(0)
                v = self.carried
                self.carried = Val("", "")
                if not ended:
                    self.ret_(Val(v.v, self.ret))
            self.term = True
        elif k == "break" or k == "continue":
            if len(self.loops) == 0:
                self.err(f"'{k}' outside loop")
            self.leave(self.wdepth[-1])
            if k == "break" and not self.term:
                self.brks[-1].append(dict(self.narrowed))
            self.br(self.loops[-1].exit if k == "break" else self.loops[-1].step)
        elif k == "global":
            for nm in n.kids:
                self.gdecl[nm.s] = True
        elif k == "assert" and (self.static(n.kids[0]) == 0 or n.kids[0].kind == "False"):
            # an assertion that cannot hold (assert x is not None with x None, assert False): code
            # after it never runs
            self.assert_fails(n)
            self.term = True
        elif k == "assert" and self.static(n.kids[0]) == 1:
            pass
        elif k == "assert":
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.cond(n.kids[0]), l2, l1)
            self.place(l1)
            self.assert_fails(n)
            self.place(l2)
            self.narrow_by(n.kids[0], True)
        elif k == "raise":
            self.raise_stmt(n)
        elif k == "try":
            self.try_(n)
        elif k == "del":
            for dt in n.kids:
                if dt.kind == "name":
                    self.del_name(dt)
                    continue
                o = self.expr(dt.kids[0], "") if dt.kind == "index" else Val("", "")
                nodel = "TypeError: 'NoneType' object does not support item deletion"
                if is_list(unopt(o.t)):
                    ix = self.ival(dt.kids[1])
                    self.rt("pys_list_del", "void", [f"ptr {self.unwrap(o, nodel).v}", f"i64 {ix.v}"])
                elif is_dict(unopt(o.t)):
                    # del d[k] looks k up as d[k] does (dkey): a key that may be None raises
                    # KeyError: None (nonekey), and a bool deletes the int key it equals
                    kt = targs(unopt(o.t))[0]
                    kval = self.expr(dt.kids[1], kt)
                    kx = self.dkey(kval, kt)
                    key = self.to_slot(kx)
                    o = self.unwrap(o, nodel)
                    if bool_for_int(kval.t, kt):
                        self.bool_find(o.v, kval, key)
                    self.nonekey(kx, "", "pys_dict_pop", [f"ptr {o.v}", "i64 " + key])
                elif o.t in self.classes:
                    # del o[k]: o.__delitem__(k)
                    ik = self.expr(dt.kids[1], self.argtype(o.t, "__delitem__", 1, f"'{tname(o.t)}' object doesn't support item deletion"))
                    self.notnone(o, nodel)
                    self.protocol(o, "__delitem__", [ik])
                else:
                    self.err("only 'del list[i]' and 'del dict[key]' are supported")
        elif k == "with":
            # with open(p) as f: the file closes when the block is left, at its end or through
            # break, continue or return. In a program that has a try, an exception that leaves
            # the block closes it too: it is an unwind action while the block runs (a landing pad
            # runs it, and so does an exception that nothing catches); in another, an error ends
            # the program, and exit flushes every file
            n0 = len(self.exits)
            for it in n.kids[:-1]:
                v = self.expr(it.kids[0], "")
                if v.t != "file":
                    self.err(f"'with' is supported for files only (with open(...) as f:), not {v.t}")
                if not self.open_call(it.kids[0]):
                    # (a file's __enter__ raises if it is closed)
                    c = self.rt("pys_file_closed", "i64", [f"ptr {v.v}"])
                    self.guard(self.ins(f"icmp ne i64 {c}, 0"), "ValueError: I/O operation on closed file.")
                if self.eh:
                    self.rt("pys_unwind_file", "void", [f"ptr {v.v}"])
                if len(it.kids) == 2:
                    self.assign(it.kids[1], v)
                self.exits.append(Exit("with", v.v, self.handler))
            self.stmts(n.kids[-1].kids)
            if not self.term:
                self.leave(n0)
            self.exits = self.exits[:n0]
        elif k == "anyall":
            hit = self.label()
            go = self.label()
            c = self.cond(n.kids[0])
            if n.s == "any":
                self.cbr(c, hit, go)
            else:
                self.cbr(c, go, hit)
            self.place(hit)
            self.emit(f"store i1 {'true' if n.s == 'any' else 'false'}, ptr {self.lcs[-1]}")
            self.br(self.loops[-1].exit)
            self.place(go)
        elif k == "lcappend":
            et = self.lct[-1]
            v = self.expr(n.kids[0], et)
            if et == "":
                self.lct[-1] = v.t
                et = v.t
            self.rt("pys_list_append", "void", [f"ptr {self.lcs[-1]}", "i64 " + self.to_slot(self.coerce(v, et))])
        elif k == "defaults" or k == "cdefaults":
            if k == "defaults":
                self.decorators(self.funcs[n.s].node, self.funcs[n.s].node.kids[3:] if self.curfn.mod != "" else [], {})
                self.hoist(self.funcs[n.s])
            else:
                self.hoist_class(self.classes[n.s])
            if n.s in self.gflag:
                self.emit(f"store i1 true, ptr @g.{n.s}.def")
        elif k == "lclass":
            self.class_effect(self.cnodes[n.line], self.unsupported[n.s])
        elif k == "import":
            for a in n.kids:
                self.aliases[a.s] = a.kids[0].s
        elif k == "uimport":
            for x in n.kids:
                if x.kind == "guard":
                    # an optional import of a module whose code raises ImportError: it returns there
                    self.emit(f"store i1 true, ptr @init.{x.s}.guard")
                    self.add(Ins("init", "", x.s))
                    self.emit(f"store i1 false, ptr @init.{x.s}.guard")
                else:
                    self.add(Ins("init", "", x.s))
        elif k == "def" or k == "class" or k == "subclass":
            if self.modlevel:
                self.err(f"a {'class' if k == 'subclass' else k} statement inside a block of a module's code (if, try, for, while, with) is not supported: only at its top level")
            self.err("nested functions and classes are not supported")
        elif k == "badimport":
            self.err(n.s)
        elif k in UNSUPPORTED:
            self.err(UNSUPPORTED[k])
        elif k != "pass":
            self.err(f"unsupported statement '{k}'")

    def nonemix(self, f: FnInfo, t: str) -> str:
        # why template f, which returns None and a t, cannot return t | None
        if "?" in t:
            k = tname(t)
            return f"{short(f.name)}() returns None and an empty {k} whose items' type it does not show; annotate its return type (-> {k}[{'T' if k == 'list' else 'K, V'}] | None)"
        return f"{short(f.name)}() returns both None and {typestr(t)}, and None/Optional is only supported for {OPTTYPES}"

    def reopt(self, t: str) -> None:
        # the template's function being compiled, which returned a T, returns None too: T | None
        if self.curfn.ll in self.retseen:
            self.err(f"cannot infer what {short(self.curfn.name)}() returns: it calls itself before a return of None shows that it returns {typestr(t)}; annotate its return type")
        if is_sopt(t) or self.reboxes(self.ret, t):
            # its returns of an int so far return its box: each gets one before its ret
            for b in self.fn.blocks:
                if len(b.code) > 0 and b.code[-1].op == "ret" and len(b.code[-1].a) == 1 and b.code[-1].a[0].t != t:
                    b.code[-1].a = [self.convert_in(b.code[-1].a[0], t, b)]
        self.ret = t
        self.curfn.ret = t

    def del_name(self, n: Node) -> None:
        # del x: x is unbound afterwards. Reads that may follow test its "is assigned" flag
        # (definite assignment marks them), so clearing the flag is all it takes.
        name = n.s
        if name in self.unsupported:
            return  # a class of an imported module that is never compiled
        if name not in self.ltype and (name in self.funcs or name in self.classes or name in self.aliases):
            # (a function's local hides the module's function, class or import of that name)
            self.err(f"del of '{name}' is not supported: only variables can be deleted")
        if not self.modlevel and self.is_global(name):
            self.err(f"del of the global '{name}' in a function is not supported")
        if owner(name) != self.curfn.mod:
            self.err(f"del of module {owner(name)}'s attribute '{short(name)}' is not supported")
        self.nonecmp = True  # (a local only None was assigned to may be deleted)
        self.read(n)  # del of a name that is not bound raises as its read does
        self.nonecmp = False
        self.narrowed.pop(name, False)
        if name in self.ltype and name in self.lflag:
            self.emit(f"store i1 false, ptr {self.lflag[name]}")
        elif name not in self.ltype and name in self.gflag:
            self.emit(f"store i1 false, ptr @g.{name}.def")

    def augassign(self, n: Node) -> None:
        t = n.kids[0]
        op = n.s
        if t.kind == "name" and op == "+" and is_list(self.rtype(t.s)) and "?" in self.qtype(t.s):
            # xs += [...] on an empty list without a type
            self.allowq = True
            cur = self.read(t)
            self.allowq = False
            v = self.expr(n.kids[1], "")
            if not is_list(v.t):
                self.err(f"cannot extend a list with {v.t}")
            self.refine(t.s, v.t)
            self.rt("pys_list_extend", "void", [f"ptr {cur.v}", f"ptr {v.v}"])
            self.store_name(t.s, Val(cur.v, v.t))  # (the right operand may have rebound the name)
        elif t.kind == "name":
            cur = self.read(t)
            self.store_name(t.s, self.inplace(op, cur, n.kids[1]))
        elif t.kind == "attr" and self.dotted(t) != "":
            self.err(f"assigning to {self.dotted(t)} is not supported; change its value in place")
        elif t.kind == "attr" and t.kids[0].kind == "name" and t.kids[0].s in self.classes and t.kids[0].s not in self.ltype:
            # C.x op= v: the class variable's value, then the new one stored back
            ci = self.cvar(t.kids[0], t.s)
            self.class_store(ci, t.s, self.inplace(op, self.class_attr(t.kids[0], t.s), n.kids[1]))
        elif t.kind == "attr":
            o = self.expr(t.kids[0], "")
            p = self.field(o, t.s, False)
            self.frozen(o.t, t.s)
            cur = self.getfield(o, p, t.s)
            self.setfield(o, p, t.s, self.inplace(op, cur, n.kids[1]))
        elif t.kind == "index":
            o = self.expr(t.kids[0], "")
            sub = "TypeError: 'NoneType' object is not subscriptable"
            if is_list(unopt(o.t)):
                et = elem(unopt(o.t))
                i = self.ival(t.kids[1])
                o = self.unwrap(o, sub)
                cur = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"]), et)
                r = self.coerce(self.inplace(op, cur, n.kids[1]), et)
                self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {i.v}", "i64 " + self.to_slot(r)])
            elif is_dict(unopt(o.t)):
                # d[k] op= v stores k where d[k] has found it: k is looked up as d[k] does (dkey),
                # so a key that may be None raises KeyError: None, past which it is a key of d's
                # type; a bool where the keys are ints is rejected as any store of one is
                # (store_key), since CPython adds it as a bool where the right operand deletes k
                kv = targs(unopt(o.t))
                kval = self.expr(t.kids[1], kv[0])
                if bool_for_int(kval.t, kv[0]):
                    self.store_key(kval, kv[0])  # (rejected)
                kx = self.dkey(kval, kv[0])
                key = "" if is_sopt(kx.t) else self.to_slot(kx)
                o = self.unwrap(o, sub)
                if is_opt(kx.t):
                    self.guard(self.ins(f"icmp eq ptr {kx.v}, null"), "KeyError: None")
                    if is_sopt(kx.t):
                        key = self.to_slot(self.deref(kx))  # (an int key is the int its box holds)
                cur = self.from_slot(self.rt("pys_dict_getitem", "i64", [f"ptr {o.v}", f"i64 {key}"]), kv[1])
                r = self.coerce(self.inplace(op, cur, n.kids[1]), kv[1])
                self.rt("pys_dict_set", "void", [f"ptr {o.v}", f"i64 {key}", "i64 " + self.to_slot(r)])
            elif o.t in self.classes:
                # o[k] op= v: o.__setitem__(k, o.__getitem__(k) op v), k evaluated once
                ik = self.expr(t.kids[1], self.argtype(o.t, "__getitem__", 1, f"'{tname(o.t)}' object is not subscriptable"))
                self.argtype(o.t, "__setitem__", 1, f"'{tname(o.t)}' object does not support item assignment")
                self.notnone(o, sub)
                cur = self.protocol(o, "__getitem__", [ik])
                self.protocol(o, "__setitem__", [ik, self.inplace(op, cur, n.kids[1])])
            else:
                self.err(f"'{o.t}' does not support item assignment")
        else:
            self.err("invalid target for augmented assignment")

    def inplace(self, op: str, cur: Val, rhs: Node) -> Val:
        # the new value of cur op= rhs: lists change in place (+= extends, *= repeats), objects
        # use __iadd__ & co when they define them, anything else is cur op rhs
        if is_list(unopt(cur.t)) and op == "+":
            b = self.expr(rhs, cur.t)
            if is_opt(cur.t) or is_opt(b.t):
                self.none_operands(op, cur, b, "+=")
                cur = Val(cur.v, unopt(cur.t))
                b = Val(b.v, unopt(b.t))
            if is_list(b.t) and b.t != cur.t and self.wider(b.t, cur.t) == cur.t:
                b = Val(b.v, cur.t)  # (as extend: the items are copied)
            self.rt("pys_list_extend", "void", [f"ptr {cur.v}", f"ptr {self.coerce(b, cur.t).v}"])
            return cur
        if is_list(unopt(cur.t)) and op == "*":
            b = self.as_int(self.expr(rhs, 'int'))
            if is_opt(cur.t):
                self.none_operands(op, cur, b, "*=")
                cur = Val(cur.v, unopt(cur.t))
            self.rt("pys_list_imul", "void", [f"ptr {cur.v}", f"i64 {self.coerce(b, 'int').v}"])
            return cur
        im = "__i" + DUNDER.get(op, "__?")[2:]
        if cur.t in self.classes and im in self.classes[cur.t].methods:
            b = self.expr(rhs, "")
            self.none_operand(op + "=", cur, b)
            return self.call_fn(self.classes[cur.t].methods[im], [cur, b], [])
        return self.arith(op, cur, self.expr(rhs, cur.t), op + "=")

    def objlen(self, v: Val) -> Val:
        r = self.as_int(self.call_fn(self.classes[v.t].methods["__len__"], [v], []))
        self.guard(self.ins(f"icmp slt i64 {r.v}, 0"), "ValueError: __len__() should return >= 0")
        return r

    def none_operand(self, op: str, a: Val, b: Val) -> None:
        # a is None: TypeError naming b's run-time type, as CPython reports it
        if a.t not in self.classes or a.v in self.nn:
            return
        lerr = self.label()
        lok = self.label()
        self.cbr(self.ins(f"icmp eq ptr {a.v}, null"), lerr, lok)
        self.place(lerr)
        m1 = self.sconst(f"unsupported operand type(s) for {op}: 'NoneType' and 'NoneType'")
        m2 = self.sconst(f"unsupported operand type(s) for {op}: 'NoneType' and '{tname(unopt(b.t))}'")
        self.raise_("TypeError", self.select(self.isnull(b), Val(m1, "str"), Val(m2, "str")))
        self.place(lok)

    def none_operands(self, op: str, a: Val, b: Val, shown: str) -> None:
        # a op b with an optional operand that is None: CPython's TypeError, which names the other
        # operand's run-time type, or for str + None and list + None its own message
        sh = shown if shown != "" else "** or pow()" if op == "**" else op
        x = unopt(a.t)
        y = unopt(b.t)
        if is_opt(a.t):
            m1 = self.sconst(f"unsupported operand type(s) for {sh}: 'NoneType' and 'NoneType'")
            m2 = self.sconst(f"unsupported operand type(s) for {sh}: 'NoneType' and '{tname(y)}'")
            if op == "*" and is_sopt(a.t) and (y == "str" or is_list(y)):
                m2 = self.sconst("can't multiply sequence by non-int of type 'NoneType'")
            lerr = self.label()
            lok = self.label()
            self.cbr(self.ins(f"icmp eq ptr {a.v}, null"), lerr, lok)
            self.place(lerr)
            self.raise_("TypeError", self.select(self.ins(f"icmp eq ptr {b.v}, null"), Val(m1, "str"), Val(m2, "str")) if is_opt(b.t) else m2)
            self.place(lok)
        if is_opt(b.t):
            msg = f"unsupported operand type(s) for {sh}: '{tname(x)}' and 'NoneType'"
            if op == "+" and x == y and (x == "str" or is_list(x)):
                msg = "'NoneType' object is not iterable" if sh == "+=" and is_list(x) else f'can only concatenate {tname(x)} (not "NoneType") to {tname(x)}'
            elif op == "*" and (x == "str" or is_list(x)):
                msg = "can't multiply sequence by non-int of type 'NoneType'"
            self.guard(self.ins(f"icmp eq ptr {b.v}, null"), "TypeError: " + msg)

    def hide(self, names: list[str]) -> None:
        # comprehension variables shadow outer names once the iterable has been evaluated
        for nm in names:
            if nm in self.ltype:
                del self.ltype[nm]
            self.compvars[nm] = self.compvars.get(nm, 0) + 1

    def for_(self, n: Node, hide: list[str]) -> None:
        tgt = n.kids[0]
        it = n.kids[1]
        body = n.kids[2].kids
        names: list[str] = []
        names_in(tgt, names)
        for nm in names:
            if nm in self.nonevars and nm not in self.ltype and nm not in hide:
                self.err(f"'{nm}' is None here, and binding it as a for loop's target is not supported")
        if it.kind == "call" and it.kids[0].kind == "name" and not self.bound(it.kids[0].s):
            fn = it.kids[0].s
            args = it.kids[1:]
            if fn == "range":
                vs = self.range_args(args)
                self.for_range(tgt, vs[0], vs[1], vs[2], body, hide)
                return
            if fn == "reversed" and len(args) == 1 and args[0].kind == "call" and args[0].kids[0].kind == "name" and args[0].kids[0].s == "range" and not self.bound("range"):
                self.for_rrange(tgt, self.range_args(args[0].kids[1:]), body, hide)
                return
            for a in args:
                if self.iterator_call(a) and (fn == "enumerate" or fn == "zip" or fn == "reversed"):
                    self.err(f"{a.kids[0].s}() cannot be nested in {fn}() here; make it a list first, list({a.kids[0].s}(...))")
                if a.kind == "kw" and fn == "zip":
                    self.err(f"zip({a.s}=...) is not supported")
            if ((fn == "enumerate" or fn == "reversed") and len(args) == 1) or (fn == "zip" and len(args) > 0):
                evs: list[Val] = []
                for a in args:
                    v = self.expr(a, "")
                    if fn == "reversed" and v.t in self.classes and v.t not in self.nts:
                        # (CPython calls __reversed__, or __len__ and __getitem__, never __iter__)
                        self.err(f"'{tname(v.t)}' object is not reversible" if "__getitem__" not in self.classes[v.t].methods else f"reversed() of {short(v.t)} by its __len__ and __getitem__ is not supported")
                    evs.append(v if is_opt(v.t) or v.t in self.classes else self.iterable(v))  # (None raises, and __iter__ runs, once all are evaluated)
                notit = "TypeError: 'NoneType' object is not reversible" if fn == "reversed" else "TypeError: 'NoneType' object is not iterable"
                seqs = [self.iterable(v, notit) for v in evs]
                self.for_seq(tgt, seqs, fn, body, "0", hide)
                for i in range(len(args)):
                    self.close_temp(args[i], seqs[i])
                return
            if fn == "enumerate" and len(args) == 2 and (args[1].kind != "kw" or args[1].s == "start"):
                seq = self.expr(args[0], "")
                seq = seq if is_opt(seq.t) or seq.t in self.classes else self.iterable(seq)
                a1 = args[1].kids[0] if args[1].kind == "kw" else args[1]
                st = self.ival(a1).v
                seq = self.iterable(seq)
                self.for_seq(tgt, [seq], fn, body, st, hide)
                self.close_temp(args[0], seq)
                return
        if it.kind == "call" and len(it.kids) == 1 and it.kids[0].kind == "attr":
            m = it.kids[0].s
            if m == "items" or m == "keys" or m == "values":
                o = self.unwrap(self.expr(it.kids[0].kids[0], ""), f"AttributeError: 'NoneType' object has no attribute '{m}'")
                if is_dict(o.t):
                    self.for_seq(tgt, [o], m, body, "0", hide)
                else:
                    self.for_seq(tgt, [self.method(o, m, [])], "", body, "0", hide)
                return
        seq = self.iterable(self.expr(it, ""))
        if seq.t == "tuple[]":
            return  # nothing to iterate: the body never runs (and its types are unknown)
        self.for_seq(tgt, [seq], "", body, "0", hide)
        self.close_temp(it, seq)

    def iterable(self, v: Val, msg: str = "TypeError: 'NoneType' object is not iterable") -> Val:
        # a tuple is iterated as a list of its items, which must then share one type, an object as
        # the list its __iter__ steps through; None raises msg
        v = self.unwrap(v, msg)
        if v.t in self.nts:
            self.notnone(v, msg)
            v = self.ntup(v, True)  # (the tuple of its fields)
        if v.t in self.classes:
            return self.obj_iter(v, msg, f"'{tname(v.t)}' object is not iterable")
        if not is_tuple(v.t) or v.t == "tuple[]":
            return v
        ts = targs(v.t)
        for x in ts:
            if x != ts[0]:
                self.err(f"cannot iterate over {v.t}: its items have different types")
        return self.as_list(v, "iter")

    def ival(self, n: Node, none: str = "") -> Val:
        # an index, slice bound or range() argument: an int, or a bool used as one (as CPython does);
        # an int | None that is None raises none ("Kind: text")
        v = self.expr(n, "int")
        if is_sopt(v.t) and none != "":
            v = self.unwrap(v, none)
        return self.coerce(self.as_int(v), "int")

    def range_args(self, args: list[Node]) -> list[str]:
        vs: list[str] = []
        for a in args:
            vs.append(self.ival(a, "TypeError: 'NoneType' object cannot be interpreted as an integer").v)
        if len(vs) == 1:
            vs.insert(0, "0")
        if len(vs) == 2:
            vs.append("1")
        if len(vs) != 3:
            self.err("range() takes 1 to 3 arguments")
        return vs

    def for_range(self, tgt: Node, start: str, stop: str, step: str, body: list[Node], hide: list[str]) -> None:
        self.hide(hide)
        after = self.forget(body, tgt)
        if step.startswith("%") or int(step) == 0:
            self.guard(self.ins(f"icmp eq i64 {step}, 0"), "ValueError: range() arg 3 must not be zero")
        ctr = self.alloca("int", "")
        self.emit(f"store i64 {start}, ptr {ctr}")
        lc = self.label()
        lb = self.label()
        ls = self.label()
        le = self.label()
        lp = Loop("range", lc, lb, ls, le)
        lp.ctr = ctr
        lp.stop = Val(stop, "int")
        self.fn.loops.append(lp)
        self.place(lc)
        i = self.ins(f"load i64, ptr {ctr}")
        if not step.startswith("%"):
            c = self.ins(f"icmp {'slt' if int(step) > 0 else 'sgt'} i64 {i}, {stop}")
        else:
            up = self.ins(f"icmp slt i64 {i}, {stop}")
            dn = self.ins(f"icmp sgt i64 {i}, {stop}")
            pos = self.ins(f"icmp sgt i64 {step}, 0")
            c = self.select(pos, Val(up, "bool"), Val(dn, "bool"))
        self.cbr(c, lb, le)
        self.place(lb)
        self.assign(tgt, Val(i, "int"))
        self.loop(body, lp)
        self.place(ls)
        # a step that overflows 64 bits has passed any stop value: the loop is over
        r = self.checked("+", i, step)
        self.emit(f"store i64 {r[0]}, ptr {ctr}")
        self.cbr(r[1], le, lc)
        self.place(le)
        self.narrowed = after

    def for_rrange(self, tgt: Node, vs: list[str], body: list[Node], hide: list[str]) -> None:
        # reversed(range(a, b, s)): the range's items from the last, a + k*s for k = len-1 .. 0
        # (the length is unsigned, and the arithmetic wraps: every result is an item of the range)
        self.hide(hide)
        after = self.forget(body, tgt)
        n = self.rt("pys_range_len", "i64", [f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"])
        ctr = self.alloca("int", "")
        self.emit(f"store i64 {n}, ptr {ctr}")
        lc = self.label()
        lb = self.label()
        ls = self.label()
        le = self.label()
        lp = Loop("rrange", lc, lb, ls, le)
        lp.ctr = ctr
        self.fn.loops.append(lp)
        self.place(lc)
        c = self.ins(f"load i64, ptr {ctr}")
        self.cbr(self.ins(f"icmp ne i64 {c}, 0"), lb, le)
        self.place(lb)
        k = self.ins(f"sub i64 {c}, 1")
        self.emit(f"store i64 {k}, ptr {ctr}")
        self.assign(tgt, Val(self.ins(f"add i64 {vs[0]}, {self.ins(f'mul i64 {k}, {vs[2]}')}"), "int"))
        self.loop(body, lp)
        self.place(ls)
        self.br(lc)
        self.place(le)
        self.narrowed = after

    def for_seq(self, tgt: Node, seqs: list[Val], mode: str, body: list[Node], start: str, hide: list[str]) -> None:
        self.hide(hide)
        after = self.forget(body, tgt)
        # One loop serves lists, strings, dicts, enumerate, zip and reversed. Each round takes
        # the next item of every sequence, in order, the way its CPython iterator would: lists
        # and strings by index, checked against their current length (reversed: counting down
        # from the length at the start); dicts by entry position, skipping deleted entries and
        # failing if the dict changed size. The loop ends at the first exhausted sequence.
        ctr = self.alloca("int", "")
        self.emit(f"store i64 0, ptr {ctr}")
        st: list[str] = []
        used: list[str] = []
        for s in seqs:
            if not (s.t == "str" or is_list(s.t) or is_dict(s.t) or (s.t == "file" and mode != "reversed")):
                self.err(f"cannot iterate over {s.t}" if s.t != "file" else "a file is not reversible")
            if s.t == "file":
                st.append("")
                used.append("")
                continue
            n0 = self.ins(f"load i64, ptr {s.v}")
            used.append(n0)
            if is_dict(s.t):
                pos = self.alloca("int", "")
                p0 = "0"
                if mode == "reversed":
                    p0 = self.ins(f"sub i64 {self.rt('pys_dict_end', 'i64', [f'ptr {s.v}'])}, 1")
                self.emit(f"store i64 {p0}, ptr {pos}")
                st.append(pos)
            else:
                st.append(n0)
        lc = self.label()
        ls = self.label()
        le = self.label()
        lp = Loop("seq", lc, "", ls, le)
        lp.mode = mode
        lp.seqs = seqs
        lp.ctr = ctr
        self.fn.loops.append(lp)
        self.place(lc)
        i = self.ins(f"load i64, ptr {ctr}")
        at: list[str] = []
        for k in range(len(seqs)):
            s = seqs[k]
            if s.t == "file":
                j = self.rt("pys_file_readline", "ptr", [f"ptr {s.v}"])
                ok = self.ins(f"icmp ne i64 {self.ins(f'load i64, ptr {j}')}, 0")
                nx = ""
            elif is_dict(s.t):
                p = self.ins(f"load i64, ptr {st[k]}")
                if mode == "reversed":
                    j = self.rt("pys_dict_prev", "i64", [f"ptr {s.v}", f"i64 {p}", f"i64 {used[k]}", f"i64 {i}"])
                    nx = self.ins(f"sub i64 {j}, 1")
                else:
                    j = self.rt("pys_dict_next", "i64", [f"ptr {s.v}", f"i64 {p}", f"i64 {used[k]}", f"i64 {i}"])
                    nx = self.ins(f"add i64 {j}, 1")
                ok = self.ins(f"icmp sge i64 {j}, 0")
            elif mode == "reversed":
                j = self.ins(f"sub i64 {self.ins(f'sub i64 {st[k]}, 1')}, {i}")
                # 0 <= j < the current length, as CPython's reversed iterator checks
                ok = self.ins(f"icmp ult i64 {j}, {self.ins(f'load i64, ptr {s.v}') if is_list(s.t) else st[k]}")
            else:
                j = i
                ok = self.ins(f"icmp slt i64 {i}, {self.ins(f'load i64, ptr {s.v}')}")
            go = self.label()
            self.cbr(ok, go, le)
            self.place(go)
            lp.body = go
            lp.tests.append(go)
            lp.idx.append(j)
            if is_dict(s.t):
                self.emit(f"store i64 {nx}, ptr {st[k]}")
            at.append(j)
        vals: list[Val] = []
        if mode == "enumerate":
            vals.append(Val(i if start == "0" else self.iop("+", i, start), "int"))
        for k in range(len(seqs)):
            s = seqs[k]
            j = at[k]
            if is_list(s.t):
                vals.append(self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {s.v}", f"i64 {j}"]), elem(s.t)))
            elif s.t == "str":
                vals.append(Val(self.rt("pys_str_get", "ptr", [f"ptr {s.v}", f"i64 {j}"]), "str"))
            elif s.t == "file":
                vals.append(Val(j, "str"))
            else:
                kv = targs(s.t)
                if mode != "values":
                    vals.append(self.from_slot(self.rt("pys_dict_key", "i64", [f"ptr {s.v}", f"i64 {j}"]), kv[0]))
                if mode == "values" or mode == "items":
                    vals.append(self.from_slot(self.rt("pys_dict_val", "i64", [f"ptr {s.v}", f"i64 {j}"]), kv[1]))
        if len(vals) == 1 and mode != "zip":
            self.assign(tgt, vals[0])
        elif (tgt.kind == "tuple" or tgt.kind == "list") and len(tgt.kids) == len(vals):
            for k2 in range(len(vals)):
                self.assign(tgt.kids[k2], vals[k2])
        else:
            self.assign(tgt, self.tuple_(vals))
        self.loop(body, lp)
        self.place(ls)
        nx2 = self.ins(f"add i64 {i}, 1")
        self.emit(f"store i64 {nx2}, ptr {ctr}")
        self.br(lc)
        self.place(le)
        self.narrowed = after

    # ---- narrowing: optional locals known not to be None
    def narrows(self, n: Node, truth: bool, out: list[str]) -> None:
        # the optional locals that test n shows are not None when its value is truth, as mypy
        # narrows them: x, x is not None, x != None, isinstance(x, T), and not/and/or of those
        if not self.anyopt:
            return
        k = n.kind
        if k == "unary" and n.s == "not":
            self.narrows(n.kids[0], not truth, out)
        elif k == "boolop" and (n.s == "and") == truth:
            self.narrows(n.kids[0], truth, out)
            self.narrows(n.kids[1], truth, out)
        elif k == "name" and truth and self.narrowable(n.s):
            out.append(n.s)
        elif k == "cmp" and n.kids[1].kind == "None" and n.kids[0].kind == "name" and (n.s == "is not" or n.s == "!=" or n.s == "is" or n.s == "==") and self.narrowable(n.kids[0].s):
            if (n.s == "is not" or n.s == "!=") == truth:
                out.append(n.kids[0].s)
        elif k == "call" and truth and len(n.kids) == 3 and n.kids[0].kind == "name" and n.kids[0].s == "isinstance" and n.kids[1].kind == "name" and self.narrowable(n.kids[1].s):
            if not self.bound("isinstance") and self.isinst(unopt(self.ltype[n.kids[1].s]), n.kids[2]) == 1:
                out.append(n.kids[1].s)

    def narrowable(self, name: str) -> bool:
        # a local (or parameter) of an optional type: a global or a field may change in a call
        return is_opt(self.ltype.get(name, "")) and not self.is_global(name)

    def narrow_by(self, test: Node, truth: bool) -> dict[str, bool]:
        # narrowed becomes a copy narrowed by test being truth; the state before is returned
        pre = self.narrowed
        self.narrowed = dict(pre)
        found: list[str] = []
        self.narrows(test, truth, found)
        for nm in found:
            self.narrowed[nm] = True
        return pre

    def forget(self, body: list[Node], tgt: Node) -> dict[str, bool]:
        # a loop: what it binds (in body, and its target tgt) may be None on its later passes, and
        # after it; a copy of the state after it is returned
        if len(self.narrowed) > 0:
            names: dict[str, bool] = {}
            collect(body, names)
            deleted(body, names)
            tn: list[str] = []
            names_in(tgt, tn)
            for nm in tn:
                names[nm] = True
            self.narrowed = dict(self.narrowed)
            for nm in names:
                if nm in self.narrowed:
                    del self.narrowed[nm]
        return dict(self.narrowed)

    # ---- tests the static types decide
    def static(self, n: Node) -> int:
        # 1 or 0 if n is a test whose result the static types decide and that has nothing else to
        # evaluate: isinstance(x, T), x is None and x is not None for a variable x (that is surely
        # assigned), and not/and/or of those; -1 otherwise. A template's function, compiled for its
        # argument types, can so dispatch on them as unannotated code does.
        k = n.kind
        if k == "name" and self.static_type(n) == "None":
            return 0  # a parameter whose argument is None is false
        if k == "name" and is_tuple(self.static_type(n)):
            return 0 if self.static_type(n) == "tuple[]" else 1  # (*args: the extra arguments)
        if k == "unary" and n.s == "not":
            r = self.static(n.kids[0])
            return 1 - r if r >= 0 else -1
        if k == "boolop":
            a = self.static(n.kids[0])
            if a < 0 or (a == 1) == (n.s == "or"):
                return a
            return self.static(n.kids[1])
        if k == "cmp" and (n.s == "is" or n.s == "is not") and n.kids[1].kind == "None":
            t = self.static_type(n.kids[0])
            r = -1 if t == "" or (t in self.classes and not self.knownobj(n.kids[0])) or is_opt(t) else 1 if t == "None" else 0
            return r if r < 0 or n.s == "is" else 1 - r
        if k == "call" and n.kids[0].kind == "name" and n.kids[0].s == "hasattr" and not self.bound("hasattr") and len(n.kids) == 3 and n.kids[2].kind == "str":
            t = self.static_type(n.kids[1], True)
            h = self.has(t, n.kids[2].s) if t != "" else -1
            return 1 if h == -1 and self.knownobj(n.kids[1]) else max(h, -1)
        if k == "call" and n.kids[0].kind == "name" and n.kids[0].s == "isinstance" and not self.bound("isinstance") and len(n.kids) == 3:
            t = self.static_type(n.kids[1], True)
            r = self.isinst(t, n.kids[2]) if t != "" else -1
            return 1 if r < 0 and self.knownobj(n.kids[1]) and self.only_class(t, n.kids[2]) else r
        return -1

    def knownobj(self, n: Node) -> bool:
        # is n a template's parameter whose argument is an object known not to be None (see nnp)
        return n.kind == "name" and n.s in self.curfn.nnp and self.static_type(n) in self.classes

    def has(self, t: str, a: str) -> int:
        # hasattr(x, a) for x of static type t: 1 or 0; for an object's own attribute -1 (true
        # unless it is None), or -2 for a field __init__ may leave unassigned (its flag says).
        # The builtin types have CPython 3.13's attributes.
        if a in HASATTR["any"].split():
            return 1
        if t == "None":
            return 1 if a == "__bool__" else 0
        if is_opt(t):
            r = self.has(unopt(t), a)
            if r != 1 and a == "__bool__":
                self.err(f"hasattr() of '{a}' on a {typestr(t)} is not supported")
            return -1 if r == 1 else 0  # (unless it is None)
        if t in self.classes:
            ci = self.classes[t]
            if a in ci.fflag and t + "." + a not in self.cvars:
                return -2
            if a in ci.methods or a in ci.ftypes:
                return -1
            if t in self.nts:
                self.err(f"hasattr() of '{a}' on a NamedTuple is not supported")
            if a in HASATTR["obj"].split():
                return -1
            return -1 if self.is_dc(t) and a in "__dataclass_fields__ __dataclass_params__ __match_args__".split() else 0
        b = "list" if is_list(t) else "dict" if is_dict(t) else "tuple" if is_tuple(t) else "int" if t == "bool" else t
        if b in HASATTR:
            return 1 if a in HASATTR[b].split() else 0
        self.err(f"hasattr() of '{a}' on a {tname(t)} is not supported")
        return 0

    def static_type(self, n: Node, typed: bool = False) -> str:
        # the type of a variable read that cannot fail, or "" (typed: in isinstance or hasattr)
        if n.kind != "name" or n.chk:
            return ""
        if self.whole != 0 and n.s in self.nonevars:
            # for fills, the parameter at the line of the if: None up to the line that binds it,
            # and then of a type known only once that line is compiled
            if self.whole > 0 and self.whole <= self.nonevars[n.s]:
                return "None"
            self.unsure = self.unsure or n.s not in self.ltype
            return self.ltype.get(n.s, "") if self.whole > 0 else ""
        if self.whole > 0 and typed and self.unbound_local(n.s) and n.s not in self.compvars:
            self.unsure = True  # (a local bound further on, whose type decides isinstance and hasattr)
        if (n.s in self.nonevars or n.s in self.noneglobals) and n.s not in self.ltype:
            return "None"
        if n.s in self.ltype:
            t = self.ltype[n.s]
            return unopt(t) if n.s in self.narrowed and is_opt(t) and t != NONEVAR else t
        if self.is_global(n.s) and n.s in self.gtypes and n.s not in self.gflag:
            return self.gtypes[n.s]
        return ""

    def only_class(self, t: str, c: Node) -> bool:
        # isinstance(x, c) for an object x of class t is "x is not None": c names t, alone or with
        # types x cannot have
        if c.kind == "binop" and c.s == "|":
            return self.only_class(t, mk("tuple", "", c.line, c.kids))
        if c.kind == "name" or c.kind == "attr":
            # (or tuple and Sequence for a NamedTuple)
            return (c.kind == "name" and c.s == t) or (t in self.nts and (c.s == "tuple" or c.s == "Sequence") and self.isinst(t, c) < 0)
        if c.kind != "tuple":
            return False
        n = 0
        for x in c.kids:
            if x.kind == "name" and x.s == t:
                n += 1
            elif self.isinst(t, x) != 0:
                return False
        return n > 0

    def isinst(self, t: str, c: Node) -> int:
        # isinstance(x, c) for x of static type t: 1, 0, or -1 when x's value decides (an object,
        # which may be None) or c is not a type Pystachy knows
        if c.kind == "binop" and c.s == "|":
            return self.isinst(t, mk("tuple", "", c.line, c.kids))
        if is_opt(t):
            r = self.isinst(unopt(t), c)
            return -1 if r == 1 else r  # (unless it is None)
        if c.kind == "tuple":
            r = 0
            for x in c.kids:
                y = self.isinst(t, x)
                if y == 1:
                    return 1
                if y < 0:
                    r = -1
            return r
        abc = self.typing_ref(c) if c.kind == "attr" or (c.kind == "name" and c.s not in self.classes and self.imported(c.s) != "") else ""
        if abc == "Sequence" or abc == "MutableSequence" or abc == "Mapping" or abc == "MutableMapping":
            # (collections.abc's: str and tuple, also a NamedTuple, are Sequences, list is a mutable one)
            if abc.endswith("Mapping"):
                return 1 if is_dict(t) else 0
            if is_list(t) or (abc == "Sequence" and (t == "str" or is_tuple(t))):
                return 1
            return -1 if abc == "Sequence" and t in self.nts else 0
        if c.kind != "name":
            return -1
        if c.s in self.classes:
            # (an exception of class t, or of a builtin one, may be an object of a class deriving from t)
            xc = self.classes[c.s].exc != "" and (t == "exc" or (t in self.classes and (self.derives(t, c.s) or self.derives(c.s, t))))
            return -1 if t == c.s or xc else 0
        if self.bound(c.s):
            return -1
        if c.s == "object":
            return 1
        if c.s == "int":
            return 1 if t == "int" or t == "bool" else 0
        if c.s == "bool" or c.s == "float" or c.s == "str":
            return 1 if t == c.s else 0
        if c.s == "tuple" and t in self.nts:
            return -1  # (a tuple, unless it is None)
        if c.s == "list" or c.s == "dict" or c.s == "tuple":
            return 1 if t.startswith(c.s + "[") else 0
        if c.s in "bytes bytearray memoryview set frozenset complex range slice type".split():
            return 0
        return -1

    # ---- expressions
    def cond(self, n: Node) -> str:
        if n.kind == "name" and "?" in self.rtype(n.s):
            self.allowq = True
            v = self.read(n)
            self.allowq = False
            return self.truth(v)
        if n.kind == "boolop":
            return self.boolop(n, True, "").v
        if n.kind == "unary" and n.s == "not":
            return self.ins(f"xor i1 {self.cond(n.kids[0])}, true")
        return self.truth(self.expr(n, ""))

    def truth(self, v: Val) -> str:
        t = v.t
        if t == "bool":
            return v.v
        if t == "int":
            return self.ins(f"icmp ne i64 {v.v}, 0")
        if t == "float":
            return self.ins(f"fcmp une double {v.v}, 0.0")
        if t == "str" or is_list(t) or is_dict(t):
            return self.ins(f"icmp ne i64 {self.ins(f'load i64, ptr {v.v}')}, 0")
        if t == "None":
            return "false"
        if is_tuple(t):
            return "false" if t == "tuple[]" else "true"
        if is_opt(t):
            # not None, and then the value's own truth
            nn = self.ins(f"icmp ne ptr {v.v}, null")
            e0 = self.cur
            l1 = self.label()
            l2 = self.label()
            self.cbr(nn, l1, l2)
            self.place(l1)
            r = self.truth(self.deref(v))
            e1 = self.cur
            self.br(l2)
            self.place(l2)
            ph = Ins("phi", "bool", "")
            self.incoming(ph, "false", e0)
            self.incoming(ph, r, e1)
            return self.phi(ph)
        nz = self.ins(f"icmp ne ptr {v.v}, null")
        if t in self.classes and ("__bool__" in self.classes[t].methods or "__len__" in self.classes[t].methods):
            # None is false; otherwise __bool__, else __len__() != 0
            l1 = self.label()
            l2 = self.label()
            e1 = self.cur
            self.cbr(nz, l1, l2)
            self.place(l1)
            ms = self.classes[t].methods
            if "__bool__" in ms:
                r = self.coerce(self.call_fn(ms["__bool__"], [Val(v.v, t)], []), "bool").v
            else:
                r = self.ins(f"icmp ne i64 {self.objlen(Val(v.v, t)).v}, 0")
            e2 = self.cur
            self.br(l2)
            self.place(l2)
            ph = Ins("phi", "bool", "")
            self.incoming(ph, "false", e1)
            self.incoming(ph, r, e2)
            return self.phi(ph)
        return nz

    def expr(self, n: Node, want: str) -> Val:
        self.line = n.line
        k = n.kind
        if k == "int":
            neg = n.s.startswith("-")
            d = n.s[1:] if neg else n.s
            if len(d) > 19 or (len(d) == 19 and d > ("9223372036854775808" if neg else "9223372036854775807")):
                self.err("integer literal does not fit in 64 bits")
            return Val(n.s, "int")
        if k == "float":
            return Val(fbits(n.s), "float")
        if k == "str":
            self.modchk(n)
            return Val(self.sconst(n.s), "str")
        if k == "True" or k == "False":
            return Val(k.lower(), "bool")
        if k == "None":
            return Val("null", "None")
        if k == "name" and (is_opt(want) or want in self.classes) and want != NONEVAR and self.ltype.get(n.s, "") == NONEVAR:
            # a local only None has been assigned so far, where a T | None is expected
            t0 = self.none_type(n.s)
            self.ltype[n.s] = t0 if t0 != "" else want
        if is_opt(want) and k != "ifexp" and k != "boolop":
            want = unopt(want)  # (what types an empty display is the type a value would hold)
        if k == "name":
            if "?" not in want and same_kind(want, self.ltype.get(n.s, "")) and self.unfilled(n.s):
                self.refine(n.s, want)  # an empty container that nothing fills takes the type expected here
            self.modchk(n)
            return self.read(n)
        if k == "badattr":
            self.err(n.s)  # a module attribute that does not exist, or a module used as a value
        if k in UNSUPPORTED:
            self.err(UNSUPPORTED[k])
        if k == "binop" and n.s == "%" and n.kids[0].kind == "str":
            return self.percent(n.kids[0].s, n.kids[1])
        if k == "binop":
            a = self.expr(n.kids[0], want)
            return self.arith(n.s, a, self.expr(n.kids[1], a.t))
        if k == "unary":
            return self.unary(n)
        if k == "boolop":
            return self.boolop(n, False, want)
        if k == "cmp":
            return self.compare(n)
        if k == "ifexp":
            return self.ifexp(n, want)
        if k == "call":
            return self.call(n, want)
        if k == "attr":
            path = self.dotted(n)
            if path != "" and path[: path.rfind(".")] not in MODATTRS:
                return self.modattr(path)
            tc = n.kids[0]
            if n.s == "__name__" and tc.kind == "call" and len(tc.kids) == 2 and tc.kids[0].kind == "name" and tc.kids[0].s == "type" and not self.bound("type"):
                # type(e).__name__ of an exception: its class's name
                v = self.expr(tc.kids[1], "")
                if v.t == "exc":
                    return Val(self.rt("pys_exc_name", "ptr", [f"ptr {v.v}"]), "str")
                if v.t in self.classes and self.classes[v.t].exc != "":
                    return Val(self.rt("pys_exc_cls", "ptr", [f"ptr {v.v}"]), "str")
                self.err("type(x).__name__ is only supported for exceptions")
            c = n.kids[0].s if n.kids[0].kind == "name" and n.kids[0].s not in self.ltype else ""
            if c in self.classes and ((c in self.nts and n.s == "_fields") or (c not in self.nts and n.s in self.classes[c].fdefault)):
                return self.class_attr(n.kids[0], n.s)
            if c in self.classes and n.s == "__name__":
                self.class_ready(n.kids[0])
                return Val(self.sconst(short(c)), "str")  # (C.__name__, and cls.__name__ in a class method)
            if c in self.classes:
                self.no_class_attr(c, n.s)
            o = self.expr(n.kids[0], "")
            if o.t in self.nts and n.s == "_fields":
                self.notnone(o, "AttributeError: 'NoneType' object has no attribute '_fields'")
                return self.tuple_([Val(self.sconst(x), "str") for x in self.classes[o.t].fields])
            if o.t == "file" and (n.s == "closed" or n.s == "name" or n.s == "mode"):
                r = self.rt(f"pys_file_{n.s}", "i64" if n.s == "closed" else "ptr", [f"ptr {o.v}"])
                return Val(self.ins(f"icmp ne i64 {r}, 0"), "bool") if n.s == "closed" else Val(r, "str")
            return self.getfield(o, self.field(o, n.s), n.s)
        if k == "index":
            return self.index(n)
        if k == "slice":
            if len(n.kids) == 4:
                self.err("slice steps are not supported")
            o = self.expr(n.kids[0], "")
            bnd: list[str] = []
            for x in n.kids[1:]:
                if x.kind == "omit":
                    bnd.append("-9223372036854775808")  # the runtime's "omitted" marker
                else:
                    bv = self.expr(x, "int")
                    if is_sopt(bv.t):
                        bnd.append(self.optbound(bv))  # (None: omitted)
                        continue
                    # a given bound of -2**63 clamps exactly like -2**63 + 1, which is not the marker
                    bd = self.coerce(self.as_int(bv), "int").v  # (as ival)
                    if bd.startswith("%"):
                        bd = self.select(self.ins(f"icmp eq i64 {bd}, -9223372036854775808"), Val("-9223372036854775807", "int"), Val(bd, "int"))
                    elif bd == "-9223372036854775808":
                        bd = "-9223372036854775807"
                    bnd.append(bd)
            o = self.unwrap(o, "TypeError: 'NoneType' object is not subscriptable")
            if o.t in self.classes and o.t not in self.nts and "__getitem__" not in self.classes[o.t].methods:
                self.err(f"'{tname(o.t)}' object is not subscriptable")
            if o.t in self.classes and o.t not in self.nts:
                self.err(f"slicing an object is not supported: {short(o.t)}.__getitem__ would take a slice object, which Pystachy does not have")
            if o.t != "str" and not is_list(o.t):
                self.err(f"'{o.t}' cannot be sliced")
            fn = "pys_str_slice" if o.t == "str" else "pys_list_slice"
            return Val(self.rt(fn, "ptr", [f"ptr {o.v}", f"i64 {bnd[0]}", f"i64 {bnd[1]}"]), o.t)
        if k == "list":
            et = elem(want) if is_list(want) and "?" not in want else ""
            soft = n is self.soft  # (an operand of ==: as its items are, see compare)
            items: list[Val] = []
            given = et != ""
            jt = ""
            for e in n.kids:
                v = self.expr(e, et)
                if et == "" and v.t != "None":
                    et = v.t
                jt = v.t if jt == "" else self.join(jt, v.t) or "-"  # (the items' types together)
                items.append(v)
            if not given and (is_opt(jt) or is_tuple(jt)):
                et = jt  # None among strings (or T | None among T): T | None (also as tuple items)
            if given and soft:
                for v in items:
                    et = self.wider(et, v.t) or et
            if et == "" or et == "None":
                self.err(f"cannot infer the type of {'an empty list' if len(items) == 0 else 'a list of None'}; add a type annotation")
            for v in items if not is_list(want) and et in self.classes else items[:0]:
                e0 = et
                while et in self.classes and self.classes[et].exc != "" and v.t in self.classes and not self.derives(v.t, et):
                    et = self.classes[et].base  # (exception objects of several classes: a base of them all)
                if e0 in self.classes and et not in self.classes:
                    self.err(f"objects of the exception classes {short(e0)} and {short(v.t)} in one list are not supported: no class of the program is a base of both (give them one: class Base(Exception), class {short(e0)}(Base), ...)")
            items = [self.coerce(v, et) for v in items]
            r = self.rt("pys_list_new", "ptr", [f"i64 {len(items)}"])
            for v in items:
                self.rt("pys_list_append", "void", [f"ptr {r}", "i64 " + self.to_slot(v)])
            return Val(r, f"list[{et}]")
        if k == "dict":
            kv = targs(want) if is_dict(want) and "?" not in want else ["", ""]
            soft = n is self.soft
            ks: list[Val] = []
            vs: list[Val] = []
            given = kv[1] != ""
            kgiven = kv[0] != ""
            jt = ""
            kj = ""
            for i in range(0, len(n.kids), 2):
                a = self.expr(n.kids[i], kv[0])
                if kv[0] == "":
                    kv[0] = a.t
                b = self.expr(n.kids[i + 1], kv[1])
                if kv[1] == "" and b.t != "None":
                    kv[1] = b.t
                jt = b.t if jt == "" else self.join(jt, b.t) or "-"
                kj = a.t if kj == "" else self.join(kj, a.t) or "-"
                ks.append(a)
                vs.append(b)
            if not given and (is_opt(jt) or is_tuple(jt)):
                kv[1] = jt  # None among strings (or T | None among T): T | None (also as tuple items)
            if not kgiven and is_tuple(kj):
                kv[0] = none_items(kj)
            ks = [self.store_key(x, kv[0]) for x in ks]
            if given and soft:
                for b in vs:
                    kv[1] = self.wider(kv[1], b.t) or kv[1]
            if kv[0] == "" or kv[1] == "":
                self.err(f"cannot infer the type of {'an empty dict' if len(ks) == 0 else 'a dict of None values'}; add a type annotation")
            vs = [self.coerce(x, kv[1]) for x in vs]
            if key_problem(kv[0]) != "":
                self.err(key_problem(kv[0]))
            r = self.rt("pys_dict_new", "ptr", [f"i64 {self.key_kind(kv[0])}", f"i64 {len(ks)}"])
            for i in range(len(ks)):
                self.rt("pys_dict_set", "void", [f"ptr {r}", "i64 " + self.to_slot(ks[i]), "i64 " + self.to_slot(vs[i])])
            return Val(r, f"dict[{kv[0]},{kv[1]}]")
        if k == "tuple":
            ws = targs(want) if is_tuple(want) else []
            vals: list[Val] = []
            for i in range(len(n.kids)):
                v = self.expr(n.kids[i], ws[i] if i < len(ws) else "")
                if i < len(ws) and v.t != ws[i] and self.widens(v.t, ws[i]):
                    v = Val(v.v, ws[i])  # (None as an object, T as T | None)
                elif i < len(ws) and self.converts(v.t, ws[i]) and not is_sopt(v.t):
                    v = self.coerce(v, ws[i])  # (an int as an int | None: its box)
                vals.append(v)
            return self.tuple_(vals)
        if k == "listcomp":
            if n.s == "gen":
                self.err("a generator expression is only supported as the argument of sum(), min(), max(), sorted(), list(), any(), all(), str.join() or list.extend()")
            return self.listcomp(n, want)
        if k == "fstr":
            acc = Val(self.sconst(""), "str")
            for i in range(len(n.kids)):
                part = n.kids[i]
                if part.kind == "fmt":
                    s = self.format_(self.expr(part.kids[0], ""), part.kids[1])
                elif part.kind == "str":
                    s = Val(self.sconst(part.s), "str")
                else:
                    s = self.to_str(self.expr(part, ""))  # compiler-written parts (dataclass __repr__)
                acc = s if i == 0 else Val(self.rt("pys_str_add", "ptr", [f"ptr {acc.v}", f"ptr {s.v}"]), "str")
            return acc
        self.err(f"unsupported expression '{k}'")
        return Val("", "")

    def class_attr(self, cn: Node, a: str) -> Val:
        # C.a through the class: a NamedTuple's _fields, or the value a class-body default binds
        # (instances read it until they assign the field; C.a = v is not supported)
        ci = self.class_ready(cn)
        if a == "_fields":
            return self.tuple_([Val(self.sconst(x), "str") for x in ci.fields])
        t = ci.ftypes[a]
        if is_const(ci.fdefault[a]) and cn.s + "." + a not in self.cvars:
            return self.coerce(self.expr(ci.fdefault[a], t), t)
        self.class_default(ci, a)
        return Val(self.ins(f"load {lt(t)}, ptr {ci.fglob[a]}"), t)

    def cvar_stores(self, ns: list[Node]) -> None:
        # the class attributes the program assigns through their class (C.x = v, C.x += v; a class
        # method's cls.x is C.x): those of a plain class become class variables (self.cvars), read
        # from their global by C.x and by the objects that have not assigned x themselves
        for n in ns:
            ts: list[Node] = n.kids[:-1] if n.kind == "assign" else [n.kids[0]] if (n.kind == "augassign" or n.kind == "annassign") and len(n.kids) > 0 else []
            while len(ts) > 0:
                t = ts.pop()
                if t.kind == "tuple":
                    ts.extend(t.kids)
                elif t.kind == "attr" and t.kids[0].kind == "name" and t.kids[0].s in self.classes:
                    c = t.kids[0].s
                    if not self.is_dc(c) and t.s in self.classes[c].fdefault:
                        self.cvars[c + "." + t.s] = True
                        # (and of the exception classes that share it, see cvar)
                        h = self.default_home(self.classes[c], t.s)
                        for x in self.classes.values():
                            if t.s in x.fdefault and self.default_home(x, t.s) is h:
                                self.cvars[x.name + "." + t.s] = True
            self.cvar_stores(n.kids)

    def cvar(self, cn: Node, a: str) -> ClassInfo:
        # the class that C.a = ... assigns a class variable of (see cvar_stores), checked
        c = cn.s
        if self.is_dc(c):
            self.err(f"assigning to a class attribute of {'NamedTuple' if c in self.nts else 'dataclass'} {short(c)} ({short(c)}.{a} = ...) is not supported")
        if c + "." + a not in self.cvars:
            self.err(f"type object '{short(c)}' has no attribute '{a}': adding a class attribute by assigning it is not supported (declare it in the class body, {a}: T = ...)")
        # an exception class shares the class variables it inherits with its base (default_home):
        # one global each, which the objects of both read
        ci = self.classes[c]
        h = self.default_home(ci, a)
        if h is not ci:
            how = f" (cls in class method {self.curfn.name}(), which {short(c)} inherits)" if self.curfn.deco == "classmethod" and self.curfn.cls == c and self.curfn.name not in self.body_names(ci.node) else ""
            self.err(f"assigning class attribute '{a}' through {short(c)}{how}, which inherits it from {short(h.name)}, is not supported (CPython would give {short(c)} an attribute of its own; {short(h.name)}.{a} = ... changes the one they share)")
        for x in self.classes.values():
            if a in x.fdefault and x is not ci and (self.derives(x.name, c) or self.derives(c, x.name)) and self.default_home(x, a) is not h:
                self.err(f"assigning class attribute {short(c)}.{a} is not supported where {short(x.name)} binds '{a}' in its class body too: an object's class attribute is read through the class of its static type (no dispatch on the object's class)")
        return self.class_ready(cn)

    def class_store(self, ci: ClassInfo, a: str, v: Val) -> None:
        # C.a = v through the class: its class variable's global
        self.class_default(ci, a)
        self.emit(f"store {lt(ci.ftypes[a])} {self.coerce(v, ci.ftypes[a]).v}, ptr {ci.fglob[a]}")

    def no_class_attr(self, c: str, a: str) -> None:
        # C.a where class C binds no class attribute a: CPython's AttributeError, or why it is not supported
        ci = self.classes[c]
        if ci.bad != "":
            self.err(ci.bad)
        if c in self.nts and a in ci.fields:
            self.err(f"reading a NamedTuple's field through its class ({short(c)}.{a}, a descriptor in CPython) is not supported")
        if a in ci.methods:
            self.err(f"method '{short(c)}.{a}' cannot be used as a value (call it)")
        if a in ci.fields:
            self.err(f"type object '{short(c)}' has no attribute '{a}' (its objects have the field '{a}')")
        self.err(f"type object '{short(c)}' has no attribute '{a}'")

    def class_ready(self, cn: Node) -> ClassInfo:
        # the class that name cn reads (C.a, C.m(...)), checked where its class statement may not
        # have run yet
        c = cn.s
        ci = self.classes[c]
        if ci.bad != "":
            self.err(ci.bad)
        if (cn.chk or self.foreign(c)) and c in self.gflag:
            self.guard(self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{c}.def')}, true"), self.unbound(c))
        return ci

    def class_call(self, cn: Node, m: str, args: list[Node], want: str) -> Val:
        # C.m(...): a static or class method called through its class (cls.m(...) in a class method)
        ci = self.class_ready(cn)
        if m not in ci.methods:
            self.err(f"type object '{short(cn.s)}' has no attribute '{m}'")
        f = ci.methods[m]
        if f.bad == STUB.replace("NAME", m):
            self.err(f.bad)  # (an imported module's: CPython's stub raises NotImplementedError, however it is called)
        if f.deco == "":
            self.err(f"{short(cn.s)}.{m}() is a method of its objects: calling it through the class is not supported; call it on an object, o.{m}(...)")
        self.cls_bound(f, cn.s, False)
        return self.call_fn(f, [], args, want)

    def cls_bound(self, f: FnInfo, c: str, obj: bool) -> None:
        # a class method that uses cls, called through class c (obj: through an object of c, which
        # may be of a class deriving from c): it is compiled for each class that has it, whose
        # name its cls reads (see inherit), so the call's class must be f's
        if f.deco != "classmethod" or not f.clsuse:
            return
        subs = [x.name for x in self.classes.values() if obj and x.name != c and self.derives(x.name, c)]
        if f.cls != c:
            self.err(f"calling class method {short(c)}.{f.name}() is not supported: it uses cls, and is compiled only for {short(f.cls)}, which defines it (a class that inherits it has its own only where no default value of it is evaluated when its def runs, and in the same module)")
        if len(subs) > 0:
            self.err(f"calling class method {f.name}() on an object of {short(c)}, which may be one of {short(subs[0])}, is not supported: it uses cls, which would be {short(c)} (calls are not dispatched on the object's class; call {short(c)}.{f.name}() or {short(subs[0])}.{f.name}())")

    def percent(self, fmt: str, rhs: Node) -> Val:
        # "format" % args with a constant format: each conversion becomes what format() or
        # str()/repr() of its argument gives, as CPython's printf-style formatting does
        items: list[Val] = []
        if rhs.kind == "tuple":
            for x in rhs.kids:
                items.append(self.expr(x, ""))
        else:
            v = self.ntup(self.expr(rhs, ""))  # (a NamedTuple is a tuple: its fields are the arguments)
            if is_tuple(unopt(v.t)) and is_opt(v.t):
                return self.percent_opt(fmt, v)
            if is_tuple(v.t):
                for i in range(len(targs(v.t))):
                    items.append(self.tget(v, i))
            elif is_dict(unopt(v.t)) and "%(" in fmt:
                self.err("% formatting with a mapping (%(name)s) is not supported")
            else:
                items.append(v)
        return self.pformat(fmt, items, False)

    def percent_opt(self, fmt: str, v: Val) -> Val:
        # "format" % t, t a tuple or None: the tuple's items are the arguments, None is one argument
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(self.ins(f"icmp eq ptr {v.v}, null"), l1, l2)
        self.place(l1)
        a = self.pformat(fmt, [Val("null", "None")], True)
        ph = Ins("phi", "str", "")
        if not self.term:
            self.incoming(ph, a.v, self.cur)
        self.br(l3)
        self.place(l2)
        tv = Val(v.v, unopt(v.t))
        items: list[Val] = []
        for i in range(len(targs(tv.t))):
            items.append(self.tget(tv, i))
        b = self.pformat(fmt, items, False)
        if not self.term:
            self.incoming(ph, b.v, self.cur)
        self.br(l3)
        self.place(l3)
        if len(ph.a) == 0:
            self.unreachable()
            return Val(self.sconst(""), "str")
        return Val(self.phi(ph), "str")

    def pformat(self, fmt: str, items: list[Val], rtnone: bool) -> Val:
        # fmt % items; rtnone: a None among them that a conversion cannot take raises when it runs
        # (it is a tuple's place, see percent_opt), as CPython's error
        acc = Val(self.sconst(""), "str")
        lit: list[str] = []
        used = 0
        i = 0
        while i < len(fmt):
            c = fmt[i]
            i += 1
            if c != "%":
                lit.append(c)
                continue
            if i < len(fmt) and fmt[i] == "%":
                lit.append("%")
                i += 1
                continue
            flags = ""
            while i < len(fmt) and fmt[i] in "-+ #0":
                flags += fmt[i]
                i += 1
            width = ""
            while i < len(fmt) and (fmt[i].isdigit() or fmt[i] == "*"):
                width += fmt[i]
                i += 1
            prec = ""
            if i < len(fmt) and fmt[i] == ".":
                i += 1
                prec = "."
                while i < len(fmt) and (fmt[i].isdigit() or fmt[i] == "*"):
                    prec += fmt[i]
                    i += 1
            while i < len(fmt) and fmt[i] in "hlL":
                i += 1
            if i >= len(fmt):
                self.err("ValueError: incomplete format")
            t = fmt[i]
            i += 1
            if "*" in width or "*" in prec:
                self.err("% formatting with a * width or precision is not supported")
            if t not in "sradiuxXoeEfFgGc":
                self.err(f"unsupported format character '{t}' ({ord(t):#x}) at index {i - 1}")
            if used >= len(items):
                return self.fmt_error("not enough arguments for format string")
            v = items[used]
            used += 1
            if len(lit) > 0:
                acc = self.cat(acc, Val(self.sconst("".join(lit)), "str"))
                lit = []
            if rtnone and v.t == "None" and t not in "sra":
                return self.fmt_error(self.nonefmt(t))
            if is_sopt(v.t) and t not in "sra":
                v = self.unwrap(v, "TypeError: " + self.nonefmt(t))
            acc = self.cat(acc, self.conversion(v, flags, width, prec, t))
        if used < len(items):
            return self.fmt_error("not all arguments converted during string formatting")
        if len(lit) > 0:
            acc = self.cat(acc, Val(self.sconst("".join(lit)), "str"))
        return acc

    def nonefmt(self, t: str) -> str:
        # what %-conversion t (not s, r or a) raises for None
        if t == "c":
            return "%c requires int or char"
        if t in "diuxXo":
            return f"%{t} format: {'a real number' if t in 'diu' else 'an integer'} is required, not NoneType"
        return "must be real number, not NoneType"

    def fmt_error(self, msg: str) -> Val:
        self.raise_("TypeError", self.sconst(msg))
        return Val(self.sconst(""), "str")

    def cat(self, a: Val, b: Val) -> Val:
        if a.v == self.sconst(""):
            return b
        return Val(self.rt("pys_str_add", "ptr", [f"ptr {a.v}", f"ptr {b.v}"]), "str")

    def conversion(self, v: Val, flags: str, width: str, prec: str, t: str) -> Val:
        # one %-conversion of v, as a format() spec: '-' left-aligns, '0' pads numbers with
        # zeros after the sign, '+' and ' ' are the sign options, '#' the alternate form
        if t == "s" or t == "r" or t == "a":
            sv = self.to_str(v) if t == "s" else self.repr(v) if t == "r" else Val(self.rt("pys_ascii", "ptr", [f"ptr {self.repr(v).v}"]), "str")
            if width == "" and prec == "":
                return sv
            return self.format_(sv, mk("str", ("<" if "-" in flags else ">") + width + prec, self.line, []))
        if t == "c":
            # one character, of a str or a code point (a precision, flags but '-' change nothing)
            if unopt(v.t) == "str":
                v = self.unwrap(v, "TypeError: %c requires int or char")
            v = v if v.t == "str" else self.as_int(v)
            if v.t != "str" and v.t != "int":
                self.err("%c requires int or char")
            cv = Val(self.rt("pys_pct_char" if v.t == "str" else "pys_pct_chr", "ptr", [f"{lt(v.t)} {v.v}"]), "str")
            return cv if width == "" else self.format_(cv, mk("str", ("<" if "-" in flags else ">") + width, self.line, []))
        spec = "<" if "-" in flags else ""
        spec += "+" if "+" in flags else " " if " " in flags else ""
        spec += "#" if "#" in flags else ""
        spec += "0" if "0" in flags and "-" not in flags else ""
        spec += width
        if t == "d" or t == "i" or t == "u" or t == "x" or t == "X" or t == "o":
            if prec != "":
                self.err(f"%{t} with a precision is not supported")
            if v.t == "float" and (t == "d" or t == "i" or t == "u"):
                v = Val(self.rt("pys_f2i", "i64", [f"double {v.v}"]), "int")  # %d truncates a float, as int() does
            v = self.as_int(v)
            if v.t != "int":
                self.err(f"%{t} format: {'a real number' if t in 'diu' else 'an integer'} is required, not {tname(v.t)}")
            return self.format_(v, mk("str", spec + ("d" if t == "i" or t == "u" else t), self.line, []))
        v = self.as_float(self.as_int(v))
        if v.t != "float":
            self.err(f"must be real number, not {tname(v.t)}")
        return self.format_(v, mk("str", spec + (prec if prec != "" else ".6") + t, self.line, []))

    def format_(self, v: Val, spec: Node) -> Val:
        # format(v, spec), as an f-string field computes it; spec is a str or an f-string node, or
        # format()'s argument
        empty = spec.kind == "str" and spec.s == ""
        if v.t in self.classes and "__format__" in self.classes[v.t].methods:
            sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
            if v.v not in self.nn:
                # None's own __format__ accepts only an empty spec
                self.guard(self.ins(f"icmp eq ptr {v.v}, null"), "TypeError: unsupported format string passed to NoneType.__format__")
            return self.call_fn(self.classes[v.t].methods["__format__"], [v, sv], [])
        if empty or v.t == "None":
            if not empty and spec.kind == "str":
                self.err("unsupported format string passed to NoneType.__format__")
            return self.to_str(v)
        if is_opt(v.t):
            # None's __format__ accepts only an empty spec, the value's its own (the runtime checks)
            if spec.kind == "str" and unopt(v.t) != "str" and not is_sopt(v.t):
                self.err(f"unsupported format string passed to {tname(unopt(v.t))}.__format__")
            sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
            return Val(self.rt("pys_format", "ptr", ["i64 " + self.to_slot(v), f"ptr {self.sconst(self.desc(v.t, 'repr'))}", f"ptr {sv.v}"]), "str")
        if v.t in self.classes or v.t == "file" or v.t == "exc":
            if spec.kind == "str":
                self.err(f"unsupported format string passed to {tname(v.t)}.__format__")
            # a computed spec: str(v) when it turns out empty, TypeError otherwise
            sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
            self.guard(self.ins(f"icmp ne i64 {self.ins(f'load i64, ptr {sv.v}')}, 0"), f"TypeError: unsupported format string passed to {tname(v.t)}.__format__")
            return self.to_str(v)
        if spec.kind == "str" and not self.isnum(v.t) and v.t != "str":
            self.err(f"unsupported format string passed to {tname(v.t)}.__format__")
        sv = self.coerce(self.expr(spec, "str"), "str", "format()'s spec")
        d = self.sconst(self.desc(v.t, "repr"))
        return Val(self.rt("pys_format", "ptr", ["i64 " + self.to_slot(v), f"ptr {d}", f"ptr {sv.v}"]), "str")

    def optbound(self, v: Val) -> str:
        # a slice bound that is an int | None: None is an omitted bound (the runtime's marker -2**63,
        # which a given bound of -2**63 is not: it clamps exactly like -2**63 + 1)
        e0 = self.cur
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.ins(f"icmp ne ptr {v.v}, null"), l1, l2)
        self.place(l1)
        bd = self.as_int(self.deref(v)).v
        bd = self.select(self.ins(f"icmp eq i64 {bd}, -9223372036854775808"), Val("-9223372036854775807", "int"), Val(bd, "int"))
        e1 = self.cur
        self.br(l2)
        self.place(l2)
        ph = Ins("phi", "int", "")
        self.incoming(ph, "-9223372036854775808", e0)
        self.incoming(ph, bd, e1)
        return self.phi(ph)

    def optint(self, v: Val, none: str) -> str:
        # an int | None or bool | None as an int, None giving the int constant none
        e0 = self.cur
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.ins(f"icmp ne ptr {v.v}, null"), l1, l2)
        self.place(l1)
        n = self.as_int(self.deref(v)).v
        e1 = self.cur
        self.br(l2)
        self.place(l2)
        ph = Ins("phi", "int", "")
        self.incoming(ph, none, e0)
        self.incoming(ph, n, e1)
        return self.phi(ph)

    def numkey(self, v: Val, t: str) -> list[str]:
        # number v (an int, float or bool) as the item of a list[t] (t another of them) that equals it,
        # for in, count(), index() and remove(): [its value, whether there is one ("true": always)].
        # No int equals 2.5 or nan, no float 2**53 + 1, no bool 2
        if v.t == "bool":
            return [self.as_float(v).v if t == "float" else self.as_int(v).v, "true"]
        if t == "float":
            fv = self.as_float(v).v
            if not v.v.startswith("%") and -9007199254740992 <= int(v.v) <= 9007199254740992:
                return [fv, "true"]
            inr = self.ins(f"fcmp olt double {fv}, 0x43E0000000000000")  # (2**63, where an int's float may round to)
            back = self.select(inr, Val(self.ins(f"fptosi double {fv} to i64"), "int"), Val("0", "int"))
            return [fv, self.ins(f"and i1 {inr}, {self.ins(f'icmp eq i64 {back}, {v.v}')}")]
        iv = v.v
        ok = "true"
        if v.t == "float":
            lo = self.ins(f"fcmp oge double {v.v}, 0xC3E0000000000000")
            inr = self.ins(f"and i1 {lo}, {self.ins(f'fcmp olt double {v.v}, 0x43E0000000000000')}")
            iv = self.select(inr, Val(self.ins(f"fptosi double {v.v} to i64"), "int"), Val("0", "int"))
            back = self.ins(f"sitofp i64 {iv} to double")
            ok = self.ins(f"and i1 {inr}, {self.ins(f'fcmp oeq double {back}, {v.v}')}")
        if t == "bool":
            b01 = self.ins(f"icmp ult i64 {iv}, 2")
            ok = b01 if ok == "true" else self.ins(f"and i1 {ok}, {b01}")
            iv = self.ins(f"trunc i64 {iv} to i1")
        return [iv, ok]

    def tuple_(self, vals: list[Val]) -> Val:
        p = self.rt("pys_alloc", "ptr", [f"i64 {8 * len(vals)}"])
        ts: list[str] = []
        for i in range(len(vals)):
            s = self.to_slot(vals[i])
            q = self.ins(f"getelementptr i64, ptr {p}, i64 {i}")
            self.emit(f"store i64 {s}, ptr {q}")
            ts.append(vals[i].t)
        return Val(p, f"tuple[{','.join(ts)}]")

    def tget(self, v: Val, i: int) -> Val:
        p = self.ins(f"getelementptr i64, ptr {v.v}, i64 {i}")
        return self.from_slot(self.ins(f"load i64, ptr {p}"), targs(v.t)[i])

    def index(self, n: Node) -> Val:
        o = self.expr(n.kids[0], "")
        t = unopt(o.t)
        sub = "TypeError: 'NoneType' object is not subscriptable"  # (once the index is evaluated)
        if is_list(t) or t == "str":
            i = self.ival(n.kids[1], "TypeError: list indices must be integers or slices, not NoneType" if is_list(t) else "TypeError: string indices must be integers, not 'NoneType'")
            o = self.unwrap(o, sub)
            if t == "str":
                return Val(self.rt("pys_str_get", "ptr", [f"ptr {o.v}", f"i64 {i.v}"]), "str")
            return self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"]), elem(t))
        if is_dict(t):
            kv = targs(t)
            kval = self.expr(n.kids[1], kv[0])
            kx = self.dkey(kval, kv[0])
            o = self.unwrap(o, sub)
            if bool_for_int(kval.t, kv[0]):
                key = self.to_slot(kx)
                return self.from_slot(self.rt("pys_dict_val", "i64", [f"ptr {o.v}", f"i64 {self.bool_find(o.v, kval, key)}"]), kv[1])
            return self.from_slot(self.nonekey(kx, "", "pys_dict_getitem", [f"ptr {o.v}", f"i64 {self.to_slot(kx)}"]), kv[1])
        if is_tuple(t) or t in self.nts:
            ts = targs(t) if is_tuple(t) else self.classes[t].fields  # (a NamedTuple's fields)
            i = self.expr(n.kids[1], "int")
            if i.t == "bool" and (i.v == "true" or i.v == "false"):
                i = Val("1" if i.v == "true" else "0", "int")
            if i.t != "int" or i.v.startswith("%"):
                self.err("tuple index must be an integer constant")
            j = int(i.v)
            if j < 0:
                j += len(ts)
            if j < 0 or j >= len(ts):
                # (rather than CPython's IndexError where it runs: the item would have no type)
                self.err(f"tuple index out of range: {i.v} for a tuple of {len(ts)} item{'s' if len(ts) != 1 else ''} (a constant index is checked at compile time)")
            if t in self.nts:
                self.notnone(o, sub)
                return self.getfield(o, self.field(o, ts[j]), ts[j])
            return self.tget(self.unwrap(o, sub), j)
        if t in self.classes:
            # o[k]: o.__getitem__(k), once k is evaluated
            ik = self.expr(n.kids[1], self.argtype(t, "__getitem__", 1, f"'{tname(t)}' object is not subscriptable"))
            self.notnone(o, sub)
            return self.protocol(o, "__getitem__", [ik])
        self.err(f"'{t}' object is not subscriptable")
        return o

    def argtype(self, t: str, m: str, j: int, missing: str) -> str:
        # the type of parameter j of the special method m of class t, which an operator calls (its
        # argument is evaluated for that type); missing: the error where t does not define m
        ms = self.classes[t].methods
        if m not in ms:
            self.err(missing)
        if ms[m].bad != "":
            self.err(ms[m].bad)  # (an imported module's method that cannot be compiled)
        return ms[m].ptypes[j] if j < len(ms[m].ptypes) else ""

    def protocol(self, o: Val, m: str, args: list[Val]) -> Val:
        # the call of the special method m of o's class that an operator makes (o[k] calls
        # __getitem__), with the arguments it has evaluated; o is known not to be None
        f = self.classes[o.t].methods[m]
        if f.npos < len(args) + 1:
            self.err(f"{m} must take {len(args)} argument{'s' if len(args) != 1 else ''} besides self")
        return self.call_fn(f, [o] + args, [])

    def obj_iter(self, v: Val, none: str, missing: str) -> Val:
        # what iterating over object v steps through: the list its __iter__ returns the iterator of
        # (see iter_ret). v None raises none ("Kind: text"); missing is the error where v's class
        # does not define __iter__ (CPython iterates by __getitem__ then, which is not supported)
        ms = self.classes[v.t].methods
        if "__iter__" not in ms and "__getitem__" in ms:
            self.err(f"iterating over {short(v.t)} by its __getitem__ is not supported (CPython calls __getitem__(0), __getitem__(1), ... until IndexError): define __iter__")
        if "__iter__" not in ms:
            self.err(missing)
        f = ms["__iter__"]
        if f.bad != "":
            self.err(f.bad)  # (an imported module's generator __iter__: its own error, not its type's)
        if not f.iters:
            self.err(f"iter() returned non-iterator of type '{tname(f.ret)}': {short(v.t)}.__iter__ must return an iterator, as iter(xs) of a list xs makes one (-> Iterator[T])")
        self.notnone(v, none)
        return self.protocol(v, "__iter__", [])

    def iter_ret(self, e: Node) -> Val:
        # return iter(x) in an __iter__ that returns an Iterator[T]: the list[T] that iterator steps
        # through, as a for loop over x would: x for a list, a new list of the items of a tuple or
        # str, the list of an object's own __iter__; an iterator other than iter()'s is not supported
        if e.kind != "call" or e.kids[0].kind != "name" or e.kids[0].s != "iter" or self.bound("iter") or len(e.kids) != 2 or e.kids[1].kind == "kw":
            self.err(f"{short(self.curfn.cls)}.__iter__ must return iter(xs) here, where xs is a list, a tuple, a str or an object with __iter__")
        v = self.iterable(self.consume(e.kids[1], self.ret))
        last = self.blk.code[-1] if len(self.blk.code) > 0 else Ins("", "", "")
        if last.op == "rt" and (last.s == "dict.keys" or last.s == "dict.values" or last.s == "dict.items") and v.v == f"%t{last.r[0]}":
            # (keys() is a list here; CPython's view iterator raises if the dict changes size)
            self.err(f"iter() of a dict's {last.s[5:]}() in __iter__ is not supported: its iterator raises if the dict changes size; return iter(list(...)) of a copy")
        if v.t == "str":
            v = Val(self.rt("pys_str_list", "ptr", [f"ptr {v.v}"]), "list[str]")
        if not is_list(v.t):
            self.err(f"iter() of {typestr(v.t)} in __iter__ is not supported: return iter(xs) of a list xs of the items")
        return v

    def listcomp(self, n: Node, want: str, mode: str = "", into: str = "") -> Val:
        # [e for t in it if c] runs as a loop appending to a fresh list (or to list into, of type
        # want, as xs.extend(e for ...) does item by item); t is scoped to it. mode any/all:
        # any(e for ...) / all(...) instead, stopping at the deciding element.
        h = Ins("", "", "")
        if mode != "":
            res = self.alloca("bool", "")
            self.emit(f"store i1 {'false' if mode == 'any' else 'true'}, ptr {res}")
        elif into != "":
            res = into
        else:
            h = self.hole("list")
            res = f"%t{h.r[0]}"
        names: list[str] = []
        names_in(n.kids[1], names)
        saved: list[str] = []
        for nm in names:
            saved.append(self.ltype.get(nm, "") + " " + self.lreg.get(nm, ""))
        app = mk("lcappend" if mode == "" else "anyall", mode, n.line, [n.kids[0]])
        body = [app]
        if len(n.kids) == 4:
            body = [mk("if", "", n.line, [n.kids[3], mk("block", "", n.line, [app]), mk("block", "", n.line, [])])]
        self.lcs.append(res)
        self.lct.append(elem(want) if is_list(want) else "")
        pre = self.narrowed  # (its variables are its own: the loop binds no outer local)
        self.for_(mk("for", "", n.line, [n.kids[1], n.kids[2], mk("block", "", n.line, body)]), names)
        self.narrowed = pre
        et = self.lct.pop()
        self.lcs.pop()
        for i in range(len(names)):
            nm = names[i]
            sp = saved[i].find(" ")
            if sp == 0:
                if nm in self.ltype:
                    del self.ltype[nm]
            else:
                self.ltype[nm] = saved[i][:sp]
                self.lreg[nm] = saved[i][sp + 1 :]
            self.compvars[nm] -= 1
            if self.compvars[nm] == 0:
                del self.compvars[nm]
        if mode != "":
            return Val(self.ins(f"load i1, ptr {res}"), "bool")
        if et == "":
            self.err("cannot infer the element type of this comprehension")
        if into == "":
            self.holes[h.k] = f"list[{et}]"
        return Val(res, f"list[{et}]")

    def ifexp(self, n: Node, want: str) -> Val:
        st = self.static(n.kids[0])
        if st >= 0:
            return self.expr(n.kids[1] if st == 1 else n.kids[2], want)
        c = self.cond(n.kids[0])
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(c, l1, l2)
        self.place(l1)
        pre = self.narrow_by(n.kids[0], True)
        a = self.expr(n.kids[1], want)
        # an arm that ends the program (sys.exit()) has no edge to the join, and no value
        e1 = "" if self.term else self.cur
        self.br(l3)
        self.place(l2)
        self.narrowed = pre
        self.narrow_by(n.kids[0], False)
        wb = want if want != "" else a.t
        if want == "" and n.kids[2].kind == "ifexp" and self.optional(a.t) != "":
            wb = self.optional(a.t)  # (x if c else y if d else None: T | None)
        b = self.expr(n.kids[2], wb)
        self.narrowed = pre
        e2 = "" if self.term else self.cur
        t = b.t if e1 == "" or (a.t == "None" and e2 != "") else a.t
        if e1 != "" and e2 != "" and a.t != b.t and (want == "" or is_opt(want)) and is_opt(self.join(a.t, b.t)):
            t = self.join(a.t, b.t)  # x if c else None: T | None
        ph = Ins("phi", t, "")
        if e1 != "":
            self.incoming(ph, self.convert_at(a, t, e1).v, e1)  # (an int as an int | None: its box, made there)
        if e2 != "":
            self.incoming(ph, self.coerce(b, t).v, e2)
        self.br(l3)
        self.place(l3)
        if t == "None":
            return Val("null", "None")  # (None either way)
        return Val(self.phi(ph), t)

    def boolop(self, n: Node, ascond: bool, want: str) -> Val:
        # Python semantics: `a or b` yields a if a is truthy, else b (same static type)
        c0 = n.kids[0]
        c1 = n.kids[1]
        if n.s == "or" and c0.kind == "cmp" and c0.s == "is" and c1.kind == "cmp" and c1.s == "==" and c0.kids[0].kind == "name" and c0.kids[1].kind == "name" and c1.kids[0].kind == "name" and c1.kids[1].kind == "name" and c0.kids[0].s == c1.kids[0].s and c0.kids[1].s == c1.kids[1].s and self.isnum(self.static_type(c0.kids[0])) and self.isnum(self.static_type(c0.kids[1])):
            # x is y or x == y, the identity-or-equality test, on numbers: x == y (numbers have no
            # identity here; see the deviation about NaN)
            return Val(self.cond(c1), "bool") if ascond else self.expr(c1, want)
        st = self.static(n.kids[0])
        if st >= 0:
            # a static test on the left: it is the value if it decides, else the right operand
            if (st == 1) == (n.s == "or"):
                return Val("true" if st == 1 else "false", "bool") if ascond else self.expr(n.kids[0], want)
            return Val(self.cond(n.kids[1]), "bool") if ascond else self.expr(n.kids[1], want)
        a = Val(self.cond(n.kids[0]), "bool") if ascond else self.expr(n.kids[0], want)
        if a.t == "None":
            # None is false: `None and b` is None without evaluating b, `None or b` is b
            if n.s == "or":
                return self.expr(n.kids[1], want)
            return Val("null", "None")
        c = self.truth(a)
        if self.term:
            self.place(self.label())
        e1 = self.cur
        l2 = self.label()
        l3 = self.label()
        if n.s == "and":
            self.cbr(c, l2, l3)
        elif is_sopt(a.t) and not ascond:
            # x or y with x an int | None: a true x is unboxed where it goes to the join (e1)
            e1 = self.label()
            self.cbr(c, e1, l2)
            self.place(e1)
            self.br(l3)
        else:
            self.cbr(c, l3, l2)
        self.place(l2)
        pre = self.narrow_by(n.kids[0], n.s == "and")
        b = Val(self.cond(n.kids[1]), "bool") if ascond else self.expr(n.kids[1], a.t)
        self.narrowed = pre
        # a right operand that ends the program (sys.exit()) has no edge to the join, and no value
        rt = a.t
        if not ascond and (is_opt(a.t) or is_opt(b.t) or b.t == "None"):
            # x or y with x T | None: a true x is a T; x or None, x and y: T | None
            rt = unopt(a.t) if n.s == "or" else a.t
            if not self.term and self.join(rt, b.t) != "":
                rt = self.join(rt, b.t)
        ph = Ins("phi", rt, "")
        self.incoming(ph, self.convert_at(a, rt, e1).v if not ascond and self.converts(a.t, rt) else a.v, e1)
        if not self.term:
            self.incoming(ph, self.coerce(b, rt).v, self.cur)
        self.br(l3)
        self.place(l3)
        return Val(self.phi(ph), rt)

    def unary(self, n: Node) -> Val:
        op = n.s
        e = n.kids[0]
        if op == "not":
            return Val(self.ins(f"xor i1 {self.cond(e)}, true"), "bool")
        if op == "-" and (e.kind == "int" or e.kind == "float"):
            return self.expr(mk(e.kind, "-" + e.s, e.line, []), "")
        v = self.expr(e, "")
        if is_sopt(v.t):
            v = self.unwrap(v, f"TypeError: bad operand type for unary {op}: 'NoneType'")
        v = self.as_int(v)
        if v.t == "int" and op == "-":
            return Val(self.iop("-", "0", v.v), "int")
        if v.t == "int" and op == "~":
            return Val(self.ins(f"xor i64 {v.v}, -1"), "int")
        if v.t == "float" and op == "-":
            return Val(self.ins(f"fneg double {v.v}"), "float")
        if (v.t == "int" or v.t == "float") and op == "+":
            return v
        m = "__neg__" if op == "-" else "__pos__" if op == "+" else "__invert__"
        if v.t in self.classes and m in self.classes[v.t].methods:
            self.err(f"unary {op} on an object ({m}) is not supported")
        self.err(f"bad operand type for unary {op}: '{tname(v.t)}'")
        return v

    def dunder(self, op: str, a: Val, b: Val, shown: str = "") -> Val:
        # operator overloading, resolved statically: a + b -> A.__add__(a, b)
        m = DUNDER.get(op, "")
        if m != "" and (a.t in self.nts or b.t in self.nts):
            r = self.ntop(op, a, b, shown)
            if r.t != "":
                return r
        if op in REFL and (a.t in self.classes or b.t in self.classes):
            return self.richcmp(op, a, b)
        if (op == "==" or op == "!=") and a.t == "None" and b.t in self.classes:
            # None == x: None's own __eq__ declines, so CPython asks x
            bm = self.classes[b.t].methods
            if m in bm and self.cmp_method(b.t, m, "None") != "":
                return self.eqcall(bm[m], op == "==", b, a)
            if op == "!=" and self.cmp_method(b.t, "__eq__", "None") != "":
                return Val(self.ins(f"xor i1 {self.eqcall(bm['__eq__'], True, b, a).v}, true"), "bool")
            return Val("", "")
        if a.t not in self.classes:
            return Val("", "")
        ms = self.classes[a.t].methods
        if m in ms and (op == "==" or op == "!=") and self.lenient and self.cmp_method(a.t, m, b.t) == "":
            return Val("", "")
        if m in ms and (op == "==" or op == "!="):
            return self.eqcall(ms[m], op == "==", a, b)
        if m in ms:
            self.none_operand(shown if shown != "" else op, a, b)
            return self.call_fn(ms[m], [a, b], [])
        if op == "!=" and "__eq__" in ms:
            return Val(self.ins(f"xor i1 {self.dunder('==', a, b).v}, true"), "bool")
        return Val("", "")

    def ntop(self, op: str, a: Val, b: Val, shown: str) -> Val:
        # a op b with a NamedTuple operand: tuple's methods, which compare it (with tuples and
        # other NamedTuples), concatenate and repeat it as the tuple of its fields, unless its class
        # defines the operator; Val("", "") where the class's own method or no method applies
        m = DUNDER[op]
        rm = DUNDER[REFL[op]] if op in REFL else m if op == "==" or op == "!=" else "__r" + m[2:]
        tl = (a.t in self.nts or is_tuple(a.t)) and (b.t in self.nts or is_tuple(b.t))
        if a.t in self.nts and m in self.classes[a.t].methods:
            if tl and a.t != b.t:
                self.err(f"{short(a.t)}.{m} with a {typestr(b.t)} operand is not supported")
            return Val("", "")
        cmp = op in REFL or op == "==" or op == "!="
        if b.t in self.nts and rm in self.classes[b.t].methods and (is_tuple(a.t) if cmp else a.t != b.t):
            # (CPython asks a tuple's subclass first, and b's __radd__ & co where a has no __add__)
            self.err(f"{short(b.t)}.{rm} with a {typestr(a.t)} operand is not supported")
        if tl and (op == "==" or op == "!="):
            return self.cmp2(op, self.ntup(a), self.ntup(b))
        if tl and cmp:
            return self.richcmp(op, a, b)
        if (op == "+" and tl) or (op == "*" and (a.t == "int" or b.t == "int")):
            sh = shown if shown != "" else op
            self.none_operand(sh, a, b)  # (None on the left)
            self.notnone(b, 'TypeError: can only concatenate tuple (not "NoneType") to tuple' if op == "+" else f"TypeError: unsupported operand type(s) for {sh}: 'int' and 'NoneType'")
            return self.arith(op, self.ntup(a, True), self.ntup(b, True), shown)
        return Val("", "")

    def ntup(self, v: Val, known: bool = False) -> Val:
        # a NamedTuple as tuple's methods see it: the tuple of its fields (a tuple | None if it
        # may be None and is not known not to be here); any other value as it is
        if v.t not in self.nts:
            return v
        ci = self.classes[v.t]
        maybe = v.v not in self.nn and not known
        l0 = self.cur
        lread = self.label() if maybe else ""
        lend = self.label() if maybe else ""
        if maybe:
            self.cbr(self.ins(f"icmp eq ptr {v.v}, null"), lend, lread)
            self.place(lread)
        t = self.tuple_([self.getfield(v, Val(self.fgep(v, ci.fpos[x]), ci.ftypes[x]), x) for x in ci.fields])
        if not maybe:
            return t
        l1 = self.cur
        self.br(lend)
        self.place(lend)
        ph = Ins("phi", self.optional(t.t), "")
        self.incoming(ph, "null", l0)
        self.incoming(ph, t.v, l1)
        return Val(self.phi(ph), ph.t)

    def cmp_method(self, t: str, m: str, other: str) -> str:
        # m, if class t defines it as a binary method that accepts an operand of type other
        if t not in self.classes or m not in self.classes[t].methods:
            return ""
        f = self.classes[t].methods[m]
        if (f.bad != "" and not self.lenient) or (f.bad == "" and len(f.params) == 2 and (f.ptypes[1] == other or (other == "None" and f.ptypes[1] in self.classes))):
            return m  # (a method that cannot be compiled: the call reports why; see desc)
        return ""

    def isnull(self, v: Val) -> str:
        # i1: is v None at run time
        if v.t == "None":
            return "true"
        if (v.t in self.classes and v.v not in self.nn) or is_opt(v.t):
            return self.ins(f"icmp eq ptr {v.v}, null")
        return "false"

    def richcmp(self, op: str, a: Val, b: Val) -> Val:
        # a < b for objects, as CPython does it: a.__lt__(b) if a defines it, else the reflected
        # b.__gt__(a), else TypeError naming both run-time types (None defines neither)
        fw = self.cmp_method(a.t, DUNDER[op], b.t)
        rf = self.cmp_method(b.t, DUNDER[REFL[op]], a.t)
        if fw == "" and rf == "" and not self.lenient and a.t in self.classes and DUNDER[op] in self.classes[a.t].methods:
            self.err(f"{DUNDER[op]}() of {shown(a.t)} takes a {typestr(self.classes[a.t].methods[DUNDER[op]].ptypes[1])}, not a {typestr(b.t)}")
        # a NamedTuple without the method compares as the tuple of its fields (see ntop): b's
        # reflected method runs only where a is None
        nt = fw == "" and (a.t in self.nts or b.t in self.nts) and (a.t in self.nts or is_tuple(a.t)) and (b.t in self.nts or is_tuple(b.t))
        if fw == "" and rf == "" and not self.lenient and not nt:
            self.err(f"'{op}' not supported between instances of '{tname(a.t)}' and '{tname(b.t)}'")
        if fw != "" and a.v in self.nn:
            return self.call_fn(self.classes[a.t].methods[fw], [a, b], [])
        lend = self.label()
        ph = Ins("phi", "bool", "")
        if nt:
            lcall = self.label()
            lnone = self.label()
            self.cbr(self.ins(f"or i1 {self.isnull(a)}, {self.isnull(b)}"), lnone, lcall)
            self.place(lcall)
            r = self.cmp2(op, self.ntup(a, True), self.ntup(b, True))
            self.incoming(ph, r.v, self.cur)
            self.br(lend)
            self.place(lnone)
        if fw != "":
            lcall = self.label()
            lnone = self.label()
            self.cbr(self.isnull(a), lnone, lcall)
            self.place(lcall)
            r = self.call_fn(self.classes[a.t].methods[fw], [a, b], [])
            self.incoming(ph, r.v, self.cur)
            self.br(lend)
            self.place(lnone)
        if rf != "":
            lcall = self.label()
            lerr = self.label()
            self.cbr(self.isnull(b), lerr, lcall)
            self.place(lcall)
            r = self.call_fn(self.classes[b.t].methods[rf], [b, a], [])
            self.incoming(ph, r.v, self.cur)
            self.br(lend)
            self.place(lerr)
        an = self.isnull(a)
        bn = self.isnull(b)
        ms: list[str] = []
        for x in ["NoneType", tname(unopt(a.t))]:
            for y in ["NoneType", tname(unopt(b.t))]:
                ms.append(self.sconst(f"'{op}' not supported between instances of '{x}' and '{y}'"))
        mn = self.select(bn, Val(ms[0], "str"), Val(ms[1], "str"))
        mf = self.select(bn, Val(ms[2], "str"), Val(ms[3], "str"))
        self.raise_("TypeError", self.select(an, Val(mn, "str"), Val(mf, "str")))
        self.place(lend)
        if len(ph.a) == 0:
            return Val("false", "bool")
        return Val(self.phi(ph), "bool")

    def eqcall(self, f: FnInfo, iseq: bool, a: Val, b: Val) -> Val:
        # a == b via __eq__ (or != via __ne__). With None on the left CPython falls back to
        # b's reflected method, or to identity when both are None.
        if a.v in self.nn:
            return self.call_fn(f, [a, b], [])
        same = "true" if iseq else "false"
        lnull = self.label()
        lcall = self.label()
        lend = self.label()
        ph = Ins("phi", "bool", "")
        self.cbr(self.ins(f"icmp eq ptr {a.v}, null"), lnull, lcall)
        self.place(lnull)
        if b.t == a.t:
            lboth = self.label()
            lrefl = self.label()
            self.cbr(self.ins(f"icmp eq ptr {b.v}, null"), lboth, lrefl)
            self.place(lboth)
            self.incoming(ph, same, lboth)
            self.br(lend)
            self.place(lrefl)
            r = self.call_fn(f, [b, a], [])
            self.incoming(ph, r.v, self.cur)
        else:
            # None == None is True; None == <anything else> is False
            self.incoming(ph, same if b.t == "None" else ("false" if iseq else "true"), lnull)
        self.br(lend)
        self.place(lcall)
        r = self.call_fn(f, [a, b], [])
        self.incoming(ph, r.v, self.cur)
        self.br(lend)
        self.place(lend)
        return Val(self.phi(ph), "bool")

    def arith(self, op: str, a: Val, b: Val, shown: str = "") -> Val:
        du = self.dunder(op, a, b, shown)
        if du.t != "":
            return du
        if is_opt(a.t) or is_opt(b.t):
            self.none_operands(op, a, b, shown)
            return self.arith(op, self.deref(a) if is_opt(a.t) else a, self.deref(b) if is_opt(b.t) else b, shown)
        if a.t == "bool" and b.t == "bool" and (op == "&" or op == "|" or op == "^"):
            return Val(self.ins(f"{IOPS[op]} i1 {a.v}, {b.v}"), "bool")
        a = self.as_int(a)
        b = self.as_int(b)
        if a.t == "int" and b.t == "int" and op == "/":
            return Val(self.rt("pys_idiv", "double", [f"i64 {a.v}", f"i64 {b.v}"]), "float")
        if a.t == "int" and b.t == "int" and op != "/":
            if op in CHECKED:
                return Val(self.iop(op, a.v, b.v), "int")
            if op in IOPS:
                return Val(self.ins(f"{IOPS[op]} i64 {a.v}, {b.v}"), "int")
            if op in IRT:
                return Val(self.rt(IRT[op], "i64", [f"i64 {a.v}", f"i64 {b.v}"]), "int")
        if (a.t == "int" or a.t == "float") and (b.t == "int" or b.t == "float"):
            x = self.as_float(a)
            y = self.as_float(b)
            if op in FOPS:
                return Val(self.ins(f"{FOPS[op]} double {x.v}, {y.v}"), "float")
            if op in FRT:
                return Val(self.rt(FRT[op], "double", [f"double {x.v}", f"double {y.v}"]), "float")
        seq = a.t == "str" or is_list(a.t)
        if op == "+" and seq and a.t == b.t:
            return Val(self.rt("pys_str_add" if a.t == "str" else "pys_list_add", "ptr", [f"ptr {a.v}", f"ptr {b.v}"]), a.t)
        if op == "+" and is_list(a.t) and is_list(b.t) and self.wider(a.t, b.t) != "":
            return Val(self.rt("pys_list_add", "ptr", [f"ptr {a.v}", f"ptr {b.v}"]), self.wider(a.t, b.t))  # (a new list)
        if op == "*" and seq and b.t == "int":
            return Val(self.rt("pys_str_mul" if a.t == "str" else "pys_list_mul", "ptr", [f"ptr {a.v}", f"i64 {b.v}"]), a.t)
        if op == "+" and is_tuple(a.t) and is_tuple(b.t):
            return self.tuple_([self.tget(a, i) for i in range(len(targs(a.t)))] + [self.tget(b, i) for i in range(len(targs(b.t)))])
        if op == "*" and is_tuple(a.t) and b.t == "int":
            if b.v.startswith("%"):
                self.err(f"{typestr(a.t)} * n needs a constant n (its length is part of its type)")
            return self.tuple_([self.tget(a, i % len(targs(a.t))) for i in range(len(targs(a.t)) * max(0, int(b.v)))])
        if op == "*" and a.t == "int" and (b.t == "str" or is_list(b.t) or is_tuple(b.t)):
            return self.arith(op, b, a)
        if op == "+" and is_list(a.t) and is_list(b.t):
            self.err(f"unsupported operand types for +: {typestr(a.t)} and {typestr(b.t)} (a list holds items of one type)")
        # CPython's TypeError, at compile time
        an = tname(a.t)
        bn = tname(b.t)
        if op == "+" and (a.t == "str" or is_list(a.t) or is_tuple(a.t)):
            self.err(f'can only concatenate {an} (not "{bn}") to {an}')
        if op == "*" and (a.t == "str" or is_list(a.t) or is_tuple(a.t) or b.t == "str" or is_list(b.t) or is_tuple(b.t)):
            self.err(f"can't multiply sequence by non-int of type '{bn if a.t == 'str' or is_list(a.t) or is_tuple(a.t) else an}'")
        self.err(f"unsupported operand type(s) for {shown if shown != '' else '** or pow()' if op == '**' else op}: '{an}' and '{bn}'")
        return a

    def compare(self, n: Node) -> Val:
        ops = n.s.split(",")
        if len(ops) == 1 and (n.kids[0].kind == "list" or n.kids[0].kind == "dict") and (len(n.kids[0].kids) == 0 or nones(n.kids[0])):
            # [] == xs, {} in ds, [None] == xs: an empty display, or one of None, takes its type
            # from the other side (it has nothing to evaluate first)
            b = self.expr(n.kids[1], "")
            w = b.t
            if ops[0] == "in" or ops[0] == "not in":
                w = elem(b.t) if is_list(b.t) else targs(b.t)[0] if is_dict(b.t) else ""
            if (ops[0] == "in" or ops[0] == "not in") and b.t in self.classes and b.t not in self.nts:
                # x in o: the type of __contains__'s parameter, or of the items __iter__ steps through
                ms = self.classes[b.t].methods
                if "__contains__" in ms:
                    w = self.argtype(b.t, "__contains__", 1, "")
                elif "__iter__" in ms and is_list(ms["__iter__"].ret):
                    w = elem(ms["__iter__"].ret)
            if len(n.kids[0].kids) > 0:
                self.soft = n.kids[0]
            return self.cmp2(ops[0], self.expr(n.kids[0], w), b)
        # (x is None reads a local that only None was assigned to so far, see none_type)
        self.nonecmp = len(ops) == 1 and n.kids[1].kind == "None" and n.kids[0].kind == "name" and (ops[0] == "is" or ops[0] == "is not" or ops[0] == "==" or ops[0] == "!=")
        a = self.expr(n.kids[0], "")
        self.nonecmp = False
        if len(ops) == 1 and (ops[0] == "in" or ops[0] == "not in") and self.iterator_call(n.kids[1]) and n.kids[1].kids[0].s == "range":
            # x in range(...): arithmetic, as CPython's range.__contains__ does for ints; an int |
            # None that is None equals no item
            nn = ""
            if is_sopt(a.t) and unopt(a.t) != "float":
                nn = self.ins(f"icmp ne ptr {a.v}, null")
                a = Val(self.optint(a, "0"), "int")
            if a.t != "int" and a.t != "bool":
                self.err(f"'in range(...)' needs an int, not {typestr(a.t)}")
            vs = self.range_args(n.kids[1].kids[1:])
            hit = self.rt("pys_range_has", "i64", [f"i64 {self.as_int(a).v}", f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"])
            if nn != "":
                hit = self.select(nn, Val(hit, "int"), Val("0", "int"))
            return Val(self.ins(f"icmp {'ne' if ops[0] == 'in' else 'eq'} i64 {hit}, 0"), "bool")
        if len(ops) == 1:
            w = a.t
            if (ops[0] == "in" or ops[0] == "not in") and n.kids[1].kind == "list" and (is_list(a.t) or is_dict(a.t)):
                w = f"list[{a.t}]"  # (xs in [[1], [2]]: a list of such)
            self.soft = n.kids[1]  # (a display there may hold what may be None where a holds none)
            return self.cmp2(ops[0], a, self.expr(n.kids[1], w))
        l3 = self.label()
        ph = Ins("phi", "bool", "")
        r = a
        for i in range(len(ops)):
            b = self.expr(n.kids[i + 1], a.t)
            r = self.cmp2(ops[i], a, b)
            if i < len(ops) - 1:
                nx = self.label()
                self.incoming(ph, "false", self.cur)
                self.cbr(r.v, nx, l3)
                self.place(nx)
            a = b
        self.incoming(ph, r.v, self.cur)
        self.br(l3)
        self.place(l3)
        return Val(self.phi(ph), "bool")

    def exc_id(self, v: Val) -> Val:
        # what an exception is, for is and ==: the object of an exception class it raises, if it
        # raises one (each raise of it makes an exception of its own), else itself
        return Val(self.rt("pys_exc_id", "ptr", [f"ptr {v.v}"]), "exc") if v.t == "exc" else v

    def exc_eq(self, t: str, what: str = "") -> None:
        # == compares exceptions (of type t, or inside t) by identity: not where an exception
        # class defines __eq__ or __ne__, which CPython calls for one that an exception may be
        if "E" in self.desc(t, "repr"):
            for c in self.classes.values():
                if c.exc != "" and ("__eq__" in c.methods or "__ne__" in c.methods):
                    m = "__eq__" if "__eq__" in c.methods else "__ne__"
                    what = what if what != "" else "between exceptions" if t == "exc" else f"between values of type {typestr(t)}"
                    self.err(f"== {what} is not supported where an exception class defines {m} ({short(c.name)} does): compare objects of the class itself, or use 'is'")

    def cmp2(self, op: str, a: Val, b: Val) -> Val:
        if (op == "==" or op == "!=") and a.t == b.t and a.t == "file":
            # files compare by identity, as CPython's do
            return Val(self.ins(f"icmp {'eq' if op == '==' else 'ne'} ptr {a.v}, {b.v}"), "bool")
        xa = a.t == "exc" or (a.t in self.classes and self.classes[a.t].exc != "")
        xb = b.t == "exc" or (b.t in self.classes and self.classes[b.t].exc != "")
        if xa and xb and a.t != b.t and a.t in self.classes and b.t in self.classes and (op == "==" or op == "!="):
            # objects of exception classes with a base class in common: as objects of that base,
            # whose __eq__ a class deriving from it cannot define again
            cb = a.t
            while cb in self.classes and not self.derives(b.t, cb):
                cb = self.classes[cb].base
            if cb in self.classes:
                a = self.coerce(a, cb)
                b = self.coerce(b, cb)
        if xa and xb and (a.t != b.t or a.t == "exc") and (op == "==" or op == "!=" or op == "is" or op == "is not"):
            # exceptions, builtin or objects of exception classes of different classes: by identity
            # (an exception class's object is an exception of its own that each raise of it makes)
            if op == "==" or op == "!=":
                x = "an exception" if a.t == "exc" else f"an object of {short(a.t)}"
                y = "an exception" if b.t == "exc" else f"an object of {short(b.t)}"
                self.exc_eq("exc", "between exceptions" if a.t == b.t else f"between {x} and {y}")
            return Val(self.ins(f"icmp {'eq' if op == '==' or op == 'is' else 'ne'} ptr {self.exc_id(a).v}, {self.exc_id(b).v}"), "bool")
        if op == "is" or op == "is not":
            if (a.t == "None") != (b.t == "None") and (not self.isref(a.t) or not self.isref(b.t)):
                # a number or bool is never None
                return Val("false" if op == "is" else "true", "bool")
            if not self.isref(a.t) or not self.isref(b.t) or (is_sopt(a.t) and b.t != "None") or (is_sopt(b.t) and a.t != "None"):
                self.err("'is' is only supported for objects and None")
            return Val(self.ins(f"icmp {'eq' if op == 'is' else 'ne'} ptr {a.v}, {b.v}"), "bool")
        du = self.dunder(op, a, b)
        if du.t != "":
            return du
        if (op == "in" or op == "not in") and is_opt(b.t):
            b = self.unwrap(b, "TypeError: argument of type 'NoneType' is not iterable")
        if (op == "in" or op == "not in") and b.t in self.nts and "__contains__" not in self.classes[b.t].methods:
            self.notnone(b, "TypeError: argument of type 'NoneType' is not iterable")
            b = self.ntup(b, True)  # (tuple's __contains__)
        if (op == "in" or op == "not in") and b.t in self.classes:
            # x in o: o.__contains__(x), true as its result is; else x is among what o's __iter__
            # steps through
            if "__contains__" not in self.classes[b.t].methods:
                b = self.obj_iter(b, "TypeError: argument of type 'NoneType' is not iterable", f"argument of type '{tname(b.t)}' is not iterable")
            else:
                self.notnone(b, "TypeError: argument of type 'NoneType' is not iterable")
                r = self.truth(self.protocol(b, "__contains__", [a]))
                return Val(r if op == "in" else self.ins(f"xor i1 {r}, true"), "bool")
        if (op == "in" or op == "not in") and b.t == "str":
            a = self.unwrap(a, "TypeError: 'in <string>' requires string as left operand, not NoneType")
        if (op == "in" or op == "not in") and a.t == "None" and (is_dict(b.t) or (is_list(b.t) and (self.optional(elem(b.t)) == "" or self.isnum(elem(b.t))) and elem(b.t) not in self.classes)):
            return Val("false" if op == "in" else "true", "bool")  # None is no key of a dict, and no number
        if (op == "in" or op == "not in") and is_opt(a.t) and ((is_dict(b.t) and unopt(a.t) == targs(b.t)[0]) or (is_sopt(a.t) and is_list(b.t) and (unopt(a.t) == elem(b.t) or self.isnum(elem(b.t))))):
            # None is no key of the dict (and no int of a list[int])
            nn = self.ins(f"icmp ne ptr {a.v}, null")
            e0 = self.cur
            l1 = self.label()
            l2 = self.label()
            self.cbr(nn, l1, l2)
            self.place(l1)
            hv = self.cmp2("in", self.deref(a), b)
            e1 = self.cur
            self.br(l2)
            self.place(l2)
            ph = Ins("phi", "bool", "")
            self.incoming(ph, "false", e0)
            self.incoming(ph, hv.v, e1)
            hv = Val(self.phi(ph), "bool")
            return hv if op == "in" else Val(self.ins(f"xor i1 {hv.v}, true"), "bool")
        if (op == "in" or op == "not in") and is_tuple(b.t):
            # CPython: for each item in order, item is x or item == x; stop at the first match
            lend = self.label()
            ph = Ins("phi", "bool", "")
            for i in range(len(targs(b.t))):
                item = self.tget(b, i)
                if not self.comparable(item.t, a.t):
                    continue
                if item.t in self.classes and self.isref(a.t):
                    nx = self.label()
                    self.incoming(ph, "true", self.cur)
                    self.cbr(self.ins(f"icmp eq ptr {item.v}, {a.v}"), lend, nx)
                    self.place(nx)
                c = self.cmp2("==", item, a)
                nx = self.label()
                self.incoming(ph, "true", self.cur)
                self.cbr(c.v, lend, nx)
                self.place(nx)
            self.incoming(ph, "false", self.cur)
            self.br(lend)
            self.place(lend)
            r = self.phi(ph)
            return Val(r if op == "in" else self.ins(f"xor i1 {r}, true"), "bool")
        if op == "in" or op == "not in":
            r = ""
            if b.t == "str":
                r = self.rt("pys_str_contains", "i64", [f"ptr {b.v}", f"ptr {self.coerce(a, 'str').v}"])
            elif is_list(b.t):
                ok = "true"
                if self.isnum(a.t) and self.isnum(unopt(elem(b.t))) and a.t != unopt(elem(b.t)):
                    nk = self.numkey(a, unopt(elem(b.t)))  # (1 in [1.0]: the item that equals it)
                    a = Val(nk[0], unopt(elem(b.t)))
                    ok = nk[1]
                et = a.t if is_opt(a.t) and unopt(a.t) == elem(b.t) else elem(b.t)  # (None is in no list[T])
                if a.t == "None" and elem(b.t) not in self.classes and self.optional(elem(b.t)) != "" and not self.isnum(elem(b.t)):
                    et = self.optional(elem(b.t))
                s = self.to_slot(self.coerce(a, et))
                self.exc_eq(et)
                r = self.rt("pys_list_find", "i64", [f"ptr {b.v}", f"i64 {s}", f"ptr {self.sconst(self.desc(et, '=='))}"])
                r = self.ins(f"add i64 {r}, 1")
                if ok != "true":
                    r = self.select(ok, Val(r, "int"), Val("0", "int"))
            elif is_dict(b.t):
                s = self.to_slot(self.dkey(a, targs(b.t)[0]))
                r = self.rt("pys_dict_has", "i64", [f"ptr {b.v}", f"i64 {s}"])
            else:
                self.err(f"'in' is not supported for {b.t}")
            return Val(self.ins(f"icmp {'ne' if op == 'in' else 'eq'} i64 {r}, 0"), "bool")
        if (is_sopt(a.t) or is_sopt(b.t)) and self.isnum(unopt(a.t)) and self.isnum(unopt(b.t)):
            return self.optcmp(op, a, b)
        if self.isnum(a.t) and self.isnum(b.t):
            if a.t != "float" and b.t != "float":
                return Val(self.ins(f"icmp {ICMP[op]} i64 {self.as_int(a).v}, {self.as_int(b).v}"), "bool")
            if a.t == "float" and b.t == "float":
                return Val(self.ins(f"fcmp {FCMP[op]} double {a.v}, {b.v}"), "bool")
            # int against float: exact, as CPython compares them (double rounding would not be)
            iv = self.as_int(b if a.t == "float" else a)
            if not iv.v.startswith("%") and -9007199254740992 <= int(iv.v) <= 9007199254740992:
                return Val(self.ins(f"fcmp {FCMP[op]} double {self.as_float(a).v}, {self.as_float(b).v}"), "bool")
            fv = a if a.t == "float" else b
            r = self.rt("pys_cmp_if", "i64", [f"i64 {iv.v}", f"double {fv.v}"])
            if a.t == "float":
                r = self.select(self.ins(f"icmp eq i64 {r}, 2"), Val("2", "int"), Val(self.ins(f"sub i64 0, {r}"), "int"))
            return Val(self.ins(MIXCMP[op].replace("R", r)), "bool")
        eq = op == "==" or op == "!="
        if eq and (a.t == "None" or b.t == "None" or (a.t == b.t and a.t in self.classes)) and self.isref(a.t) and self.isref(b.t):
            return Val(self.ins(f"icmp {ICMP[op]} ptr {a.v}, {b.v}"), "bool")
        # T and T | None (also as items): None == None, None == x is False, and None < x raises
        ct = self.wider(a.t, b.t)
        if ct == "" and self.boxwider(a.t, b.t) != "":
            # a tuple with an int where the other's item may be None: compared as a new tuple of boxes
            ct = self.boxwider(a.t, b.t)
            a = self.boxto(a, ct)
            b = self.boxto(b, ct)
        u = unopt(ct)
        if ct != "" and (u == "str" or is_list(u) or is_tuple(u) or (eq and is_dict(u)) or u == "exc"):
            self.exc_eq(ct)
            d = f"ptr {self.sconst(self.desc(ct, '==' if eq else op))}"
            sa = self.to_slot(a)
            sb = self.to_slot(b)
            if eq:
                r = self.rt("pys_eq", "i64", [f"i64 {sa}", f"i64 {sb}", d])
                return Val(self.ins(f"icmp {'ne' if op == '==' else 'eq'} i64 {r}, 0"), "bool")
            r = self.rt("pys_cmpop", "i64", [f"i64 {sa}", f"i64 {sb}", d, f"i64 {ORDOP[op]}"])
            return Val(self.ins(f"icmp ne i64 {r}, 0"), "bool")
        x = "an exception" if a.t == "exc" else a.t
        y = "an exception" if b.t == "exc" else b.t
        self.err(f"cannot compare {x} {op} {y}")
        return a

    def optcmp(self, op: str, a: Val, b: Val) -> Val:
        # a op b for numbers of which one or both may be None: == and != compare None as CPython
        # does (None equals only None), and an ordering raises its TypeError for None
        an = self.isnull(a)
        bn = self.isnull(b)
        anyn = an if bn == "false" else bn if an == "false" else self.ins(f"or i1 {an}, {bn}")
        lnone = self.label()
        lval = self.label()
        lend = self.label()
        self.cbr(anyn, lnone, lval)
        self.place(lnone)
        ph = Ins("phi", "bool", "")
        if op == "==" or op == "!=":
            both = "false" if an == "false" or bn == "false" else self.ins(f"and i1 {an}, {bn}")
            self.incoming(ph, both if op == "==" else self.ins(f"xor i1 {both}, true"), self.cur)
            self.br(lend)
        else:
            ms: list[str] = []
            for x in ["NoneType", tname(unopt(a.t))]:
                for y in ["NoneType", tname(unopt(b.t))]:
                    ms.append(self.sconst(f"'{op}' not supported between instances of '{x}' and '{y}'"))
            mn = self.select(bn, Val(ms[0], "str"), Val(ms[1], "str"))
            mf = self.select(bn, Val(ms[2], "str"), Val(ms[3], "str"))
            self.raise_("TypeError", self.select(an, Val(mn, "str"), Val(mf, "str")))
        self.place(lval)
        r = self.cmp2(op, self.deref(a) if is_opt(a.t) else a, self.deref(b) if is_opt(b.t) else b)
        self.incoming(ph, r.v, self.cur)
        self.br(lend)
        self.place(lend)
        return Val(self.phi(ph), "bool")

    def comparable(self, t: str, u: str) -> bool:
        # can t == u be true at all? (otherwise CPython just answers False)
        if t == u or (self.isnum(unopt(t)) and self.isnum(unopt(u))) or self.wider(t, u) != "":
            return True
        return (t == "None" and (u in self.classes or is_opt(u))) or (u == "None" and (t in self.classes or is_opt(t)))

    # ---- calls
    def call(self, n: Node, want: str) -> Val:
        f = n.kids[0]
        args = n.kids[1:]
        if f.kind == "badattr":
            self.err(f.s)
        for a in args:
            if a.kind == "starred" or a.kind == "dstar":
                self.err("star arguments are not supported")
        if f.kind == "name":
            self.modchk(f)
        if f.kind == "name" and f.s not in self.ltype:
            if self.unbound_local(f.s):
                self.err(f"local variable '{f.s}' is read before its first assignment; declare it first ({f.s}: T)")
            if (f.chk or self.foreign(f.s)) and f.s in self.gflag:
                # a call that may run before the def or class statement
                bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{f.s}.def')}, true")
                self.guard(bad, self.unbound(f.s))
            if f.s in self.funcs:
                return self.call_fn(self.funcs[f.s], [], args, want)
            if f.s in self.aliases and f.s not in self.gtypes:
                return self.builtin(self.aliases[f.s], args, want)
            if f.s in self.classes:
                if self.classes[f.s].exc != "":
                    return self.exc_object(f.s, args)
                if self.classes[f.s].bad != "":
                    self.err(self.classes[f.s].bad)
                o = self.new_obj(f.s)
                self.call_fn(self.classes[f.s].methods["__init__"], [o], args)
                return o
            if f.s in self.mvars:
                self.not_callable(f.s, self.gtypes.get(f.s, ""))
            if f.s in self.unsupported:
                self.err(self.unsupported[f.s])
            if f.s in EXCEPTIONS and EXCEPTIONS[f.s] != "-":
                # an exception made, not raised (raise e raises it)
                vals = self.exc_vals(self.exc_args(n))
                if f.s == "SystemExit":
                    return self.exit_value(vals)
                return self.exc_value("OSError" if f.s == "IOError" or f.s == "EnvironmentError" else f.s, vals)
            return self.builtin(f.s, args, want)
        if f.kind == "attr":
            c = self.curfn.cls
            if c != "" and self.classes[c].exc != "" and f.kids[0].kind == "name" and self.derives(c, f.kids[0].s) and f.kids[0].s != c and len(args) > 0 and args[0].kind == "name" and args[0].s == self.curfn.params[0] and (f.kids[0].s in self.classes or not self.bound(f.kids[0].s)):
                # Base.m(self, args) in a method of an exception class: super().m(args) for its base
                if f.kids[0].s != self.classes[c].base and not (self.classes[c].base == "OSError" and (f.kids[0].s == "IOError" or f.kids[0].s == "EnvironmentError")):
                    self.err(f"{f.kids[0].s}.{f.s}(self, ...) in a method of {short(c)} is supported only for its base, {short(self.classes[c].base)} (as super().{f.s}(...))")
                return self.super_call(mk("call", "", f.line, [mk("name", "super", f.line, [])]), f.s, args[1:])
            path = self.dotted(f)
            if path != "" and path[: path.rfind(".")] not in MODATTRS:
                return self.builtin(path, args, want)
            if f.kids[0].kind == "call" and f.kids[0].kids[0].kind == "name" and f.kids[0].kids[0].s == "super" and not self.bound("super"):
                return self.super_call(f.kids[0], f.s, args)
            if f.kids[0].kind == "name" and "?" in self.rtype(f.kids[0].s):
                return self.fill(f.kids[0], f.s, args, want)
            if f.kids[0].kind == "name" and f.kids[0].s in self.nts and f.kids[0].s not in self.ltype and f.s == "_make":
                self.err(f"{short(f.kids[0].s)}._make() is not supported: call {short(f.kids[0].s)}(...) with the fields")
            if f.kids[0].kind == "name" and f.kids[0].s in self.classes and f.kids[0].s not in self.ltype:
                return self.class_call(f.kids[0], f.s, args, want)
            o = self.expr(f.kids[0], self.default_want(f.kids[0], f.s, args, ""))
            r = self.method(o, f.s, args)
            if f.s != "close":
                self.close_temp(f.kids[0], o)
            return r
        if f.kind == "name":
            self.not_callable(f.s, self.ltype[f.s])
        self.err("only functions, classes and methods can be called")
        return Val("", "")

    def not_callable(self, name: str, t: str) -> None:
        # a call of variable name's value (c() for an object c), of type t: CPython's TypeError,
        # unless it has __call__; a builtin's name bound as a variable is rejected as such
        if short(name) in PYBUILTINS or t == "":
            self.err(f"'{name}' is a variable, so it cannot be called")
        if t in self.classes and "__call__" in self.classes[t].methods:
            self.err(f"calling an object ({short(t)}.__call__) is not supported")
        self.err(f"'{tname(unopt(t))}' object is not callable")

    def bound(self, s: str) -> bool:
        # a builtin's name that the program binds (a local, def, class or module-level variable)
        return s in self.ltype or s in self.funcs or s in self.classes or s in self.mvars

    def open_call(self, n: Node) -> bool:
        return n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s == "open" and not self.bound("open")

    def close_temp(self, n: Node, v: Val) -> None:
        # open(p).read(): nothing else refers to the file, so CPython closes it right after its use,
        # in its finalizer, which reports a failure and goes on
        if v.t == "file" and self.open_call(n):
            self.rt("pys_file_drop", "void", [f"ptr {v.v}"])

    def open_(self, args: list[Node]) -> Val:
        # open(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None): text files
        names = ["file", "mode", "buffering", "encoding", "errors", "newline"]
        given: dict[str, Node] = {}
        pos = 0
        for a in args:
            nm = a.s if a.kind == "kw" else names[pos] if pos < len(names) else ""
            if a.kind != "kw":
                pos += 1
            if nm == "closefd" or nm == "opener" or (a.kind != "kw" and nm == ""):
                self.err("open() supports only file, mode, buffering, encoding, errors and newline")
            if nm not in names:
                self.err(f"open() got an unexpected keyword argument '{nm}'")
            if nm in given:
                self.err(f"open() got multiple values for argument '{nm}'")
            given[nm] = a.kids[0] if a.kind == "kw" else a
        if "file" not in given:
            self.err("open() missing required argument 'file' (pos 1)")
        if "mode" in given and given["mode"].kind == "str" and given["mode"].s.find("b") >= 0:
            self.err("binary files are not supported (there is no bytes type)")
        e = given.get("errors", mk("None", "", self.line, []))
        if not (e.kind == "None" or (e.kind == "str" and e.s == "strict")):
            self.err("open(errors=...) is not supported: files are UTF-8, and decoding errors are not checked")
        e = given.get("encoding", mk("None", "", self.line, []))
        if e.kind == "str" and codec(e.s) == 0:
            self.err(f"only UTF-8 and Latin-1 files are supported, not encoding='{e.s}'")
        # every argument is evaluated in the order written, then the file is opened
        vals: dict[str, str] = {"mode": self.sconst("r"), "buffering": "-1", "encoding": "null", "newline": "null"}
        nones: list[str] = []  # optional arguments that may not be None, and what None raises
        nmsg: list[str] = []
        pos = 0
        for a in args:
            nm = a.s if a.kind == "kw" else names[pos]
            if a.kind != "kw":
                pos += 1
            x = a.kids[0] if a.kind == "kw" else a
            want = "int" if nm == "buffering" else "str"
            v = self.expr(x, want)
            if v.t == "None" and (nm == "encoding" or nm == "errors" or nm == "newline"):
                continue
            if is_opt(v.t) and (nm == "encoding" or nm == "newline"):
                v = Val(v.v, "str")  # None is the default
            elif is_opt(v.t) and (nm == "file" or nm == "mode"):
                nones.append(v.v)
                nmsg.append("TypeError: expected str, bytes or os.PathLike object, not NoneType" if nm == "file" else "TypeError: open() argument 'mode' must be str, not None")
                v = Val(v.v, "str")
            vals[nm] = self.coerce(v, want).v
        for j in range(len(nones)):
            self.guard(self.ins(f"icmp eq ptr {nones[j]}, null"), nmsg[j])
        return Val(self.rt("pys_open", "ptr", [f"ptr {vals['file']}", f"ptr {vals['mode']}", f"ptr {vals['encoding']}", f"ptr {vals['newline']}",
                                               f"i64 {vals['buffering']}"]), "file")

    def method(self, o: Val, m: str, args: list[Node]) -> Val:
        if is_opt(o.t):
            o = self.unwrap(o, f"AttributeError: 'NoneType' object has no attribute '{m}'")
        if (o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != "")) and (m == "__str__" or m == "__repr__") and len(args) == 0 and not self.curfn.ll.startswith("@x."):
            # e.__str__() is str(e): that of the class of e's object, which may derive from o.t's
            # (but for the ExcClass's own functions, see exc_helpers)
            return self.to_str(o) if m == "__str__" else self.repr(o)
        if o.t in self.classes and m == "__init__" and self.classes[o.t].exc != "":
            for c in self.classes.values():
                if c.name != o.t and self.derives(c.name, o.t) and "__init__" in c.methods and c.methods["__init__"].cls == c.name:
                    self.err(f"a call of __init__ on an object of {short(o.t)} is not supported where {short(c.name)}, deriving from it, defines __init__ again (calls are not dispatched on the object's class)")
        if o.t in self.classes:
            ci = self.classes[o.t]
            if m not in ci.methods and ci.exc != "" and m in HASATTR["any"].split() + ["add_note", "with_traceback"]:
                self.err(f"{short(o.t)} has no method {m}() of its own, and BaseException.{m}() is not supported" + (" (call super().__init__(...) in __init__)" if m == "__init__" else ""))
            if m not in ci.methods and not ((m == "_replace" or m == "_asdict") and o.t in self.nts):
                self.err(f"'{o.t}' object has no method '{m}'")
            self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{m}'")
            if m == "_asdict" and m not in ci.methods:
                return self.asdict(o, args)
            if m not in ci.methods:
                return self.replace(o, args)
            if ci.methods[m].iters:
                self.err(f"calling {short(o.t)}.__iter__() is not supported (its iterator is the list it steps through here): iterate over the object")
            self.cls_bound(ci.methods[m], o.t, True)
            return self.call_fn(ci.methods[m], [o] if ci.methods[m].deco == "" else [], args)  # (a static or class method gets no o)
        return self.bmethod(o, m, args)

    def replace(self, o: Val, args: list[Node]) -> Val:
        # p._replace(f=v, ...): a new NamedTuple with the fields given, and p's others
        ci = self.classes[o.t]
        given: dict[str, Val] = {}
        npos = len([a for a in args if a.kind != "kw"])
        for a in args:
            if a.kind != "kw":
                self.err(f"{short(o.t)}._replace() takes 1 positional argument but {npos + 1} were given")
            if a.s not in ci.ftypes:
                self.err(f"Got unexpected field names: ['{a.s}']")
            given[a.s] = self.expr(a.kids[0], ci.ftypes[a.s])
        vals: list[Val] = [self.new_obj(o.t)]
        for fl in ci.fields:
            vals.append(given[fl] if fl in given else self.getfield(o, self.field(o, fl), fl))
        self.call_fn(ci.methods["__init__"], vals, [])
        return vals[0]

    def asdict(self, o: Val, args: list[Node]) -> Val:
        # p._asdict(): a dict from its fields' names to their values, which must then share one type
        ci = self.classes[o.t]
        if len(args) > 0:
            self.err(f"{short(o.t)}._asdict() takes 1 positional argument but {len(args) + 1} were given")
        vt = ci.ftypes[ci.fields[0]]
        for fl in ci.fields:
            vt = self.wider(vt, ci.ftypes[fl])
            if vt == "":
                self.err(f"_asdict() of a NamedTuple whose fields have different types is not supported (a dict's values have one type): {short(o.t)}")
        r = self.rt("pys_dict_new", "ptr", [f"i64 {self.key_kind('str')}", f"i64 {len(ci.fields)}"])
        for fl in ci.fields:
            v = self.coerce(self.getfield(o, self.field(o, fl), fl), vt)
            self.rt("pys_dict_set", "void", [f"ptr {r}", "i64 " + self.to_slot(Val(self.sconst(fl), "str")), "i64 " + self.to_slot(v)])
        return Val(r, f"dict[str,{vt}]")

    def new_obj(self, c: str) -> Val:
        # a new object of class c, not initialized
        size = f"ptrtoint (ptr getelementptr (%C.{c}, ptr null, i32 1) to i64)"
        o = Val(self.rt("pys_alloc", "ptr", [f"i64 {size}"]), c)
        self.nn[o.v] = True
        return o

    def pcoerce(self, v: Val, t: str, f: FnInfo, j: int) -> Val:
        # argument j of f for a parameter of type t ("": a template's unannotated parameter takes any type)
        if t == "":
            return v
        what = ""
        if is_opt(v.t):
            what = f"argument {j if takes_self(f) else j + 1} of {short(f.name)}()" if j < f.npos else f"argument '{f.params[j]}' of {short(f.name)}()"
        return self.coerce(v, t, what)

    def call_fn(self, f: FnInfo, pre: list[Val], args: list[Node], want: str = "") -> Val:
        if f.bad != "":
            self.err(f.bad)  # (before its arguments, whose types may be placeholders')
        if f.ll not in self.called and f.ll in self.lazyat:
            hpush(self.wake, self.lazyat[f.ll])
        self.called[f.ll] = True
        self.arity(f, len(pre), args)
        line = self.line
        np = len(f.params)
        vals: list[Val] = []
        for i in range(np):
            vals.append(self.pcoerce(pre[i], f.ptypes[i], f, i) if i < len(pre) else Val("", ""))
        pos = len(pre)
        extra: list[Val] = []
        for a in args:
            j = pos
            e = a
            if a.kind == "starred" or a.kind == "dstar":
                self.err("star arguments are not supported")
            if a.kind != "kw" and f.vararg >= 0 and j >= f.vararg:
                extra.append(self.pcoerce(self.expr(a, f.varelem), f.varelem, f, j))
                pos += 1
                continue
            if a.kind == "kw":
                j = f.params.index(a.s)
                e = a.kids[0]
            else:
                pos += 1
            vals[j] = self.pcoerce(self.expr(e, f.ptypes[j]), f.ptypes[j], f, j)
        if f.vararg >= 0:
            vals[f.vararg] = self.tuple_(extra)
        for j in range(np):
            if vals[j].t == "":
                t = f.ptypes[j]
                if f.dglob[j] == "" and not is_const(f.defaults[j]):
                    self.early_default(f, j)
                if f.dglob[j].startswith("!"):
                    self.err(f.dglob[j][1:])
                if f.dglob[j] == "=None":
                    vals[j] = Val("null", "None")
                elif f.dglob[j] != "":
                    t = t if t != "" else f.dtypes[j]
                    vals[j] = Val(self.ins(f"load {lt(t)}, ptr {f.dglob[j]}"), t)
                else:
                    vals[j] = self.pcoerce(self.expr(f.defaults[j], t), t, f, j)
        self.line = line
        if f.generic:
            nnp: list[str] = []
            for j in range(np):
                if vals[j].t in self.classes and vals[j].v in self.nn and self.dispatches(f, f.params[j]):
                    nnp.append(f.params[j])
            f = self.instance(f, [v.t for v in vals], nnp)
        c = Ins("call", f.ret, f.ll)
        c.a = [v for v in vals if v.t != "None"]  # (an argument that is None is not passed)
        if f.noret:
            # it never returns: the code after the call is not reached, and the call's value has the
            # type its context expects (return fail("bad") in a function returning int)
            self.add(c)
            self.unreachable()
            t = want if want != "" and "?" not in want else "None"
            return Val("0" if t == "int" else fbits("0.0") if t == "float" else "false" if t == "bool" else "null", t)
        if f.ret == "None":
            self.add(c)
            return Val("null", "None")
        if f.ll in self.guessed and f.ll != self.curfn.ll:
            self.guessed[self.curfn.ll] = self.guessed[f.ll]  # (what it returns may hold a guess)
        self.put(c, 1)
        if "?" in f.ret:
            self.qused[f.ll] = True  # (a recursive call: what it returns can no longer change)
            return self.typed_empty(Val(f"%t{c.r[0]}", f.ret), want, f)
        return Val(f"%t{c.r[0]}", f.ret)

    def fname(self, f: FnInfo) -> str:
        # f as CPython's errors about a call's arguments name it, by its qualified name: a
        # NamedTuple's is P.__new__
        if f.name == "__init__" and f.cls in self.nts:
            return f"{short(f.cls)}.__new__"
        return f"{short(f.cls)}.{f.name}" if f.cls != "" else short(f.name)

    def arity(self, f: FnInfo, npre: int, args: list[Node]) -> None:
        # CPython's TypeError for a call of f whose arguments do not fit its parameters, in the order
        # its frame setup finds them: a keyword that names no parameter (or a positional-only one)
        # or one already given, too many positional arguments, then the missing positional and
        # keyword-only ones; npre values (the object of a method) come before args
        np = len(f.params)
        last = f.vararg if f.vararg >= 0 else f.npos if f.npos >= 0 else np  # (the positional parameters end there)
        given = npre
        filled: list[bool] = [False] * np
        for j in range(min(npre, last)):
            filled[j] = True
        for a in args:
            if a.kind != "kw":
                if given < last:
                    filled[given] = True
                given += 1
        kws = [a.s for a in args if a.kind == "kw"]
        for a in args:
            if a.kind != "kw":
                continue
            j = f.params.index(a.s) if a.s in f.params and a.s != (f.params[f.vararg] if f.vararg >= 0 else "") else -1
            if j < 0 or j < f.posonly:
                po = [k for k in kws if k in f.params and f.params.index(k) < f.posonly]
                if len(po) > 0:
                    self.err(f"{self.fname(f)}() got some positional-only arguments passed as keyword arguments: '{', '.join(po)}'")
                self.err(f"{self.fname(f)}() got an unexpected keyword argument '{a.s}'")
            if filled[j]:
                self.err(f"{self.fname(f)}() got multiple values for argument '{a.s}'")
            filled[j] = True
        off = 1 if f.deco == "classmethod" else 0  # (cls, which CPython counts and f.params leaves out)
        if f.vararg < 0 and given > last:
            if f.name == "__init__" and f.node.kids[0].kind == "noann" and not self.is_dc(f.cls):
                self.err(f"{short(f.cls)}() takes no arguments")
            dflt = len([j for j in range(last) if f.defaults[j].kind != "noann"])
            kwg = len([j for j in range(last, np) if filled[j]])
            takes = f"from {last + off - dflt} to {last + off}" if dflt > 0 else str(last + off)
            plural = "s" if dflt > 0 or last + off != 1 else ""
            kwonly = f" positional argument{'s' if given + off != 1 else ''} (and {kwg} keyword-only argument{'s' if kwg != 1 else ''})" if kwg > 0 else ""
            self.err(f"{self.fname(f)}() takes {takes} positional argument{plural} but {given + off}{kwonly} {'was' if given + off == 1 and kwg == 0 else 'were'} given")
        for kind in ["positional", "keyword-only"]:
            miss = [f.params[j] for j in range(np) if not filled[j] and f.defaults[j].kind == "noann" and j != f.vararg and (j < last) == (kind == "positional")]
            if len(miss) > 0:
                names = "'" + "', '".join(miss) + "'"
                if len(miss) == 2:
                    names = f"'{miss[0]}' and '{miss[1]}'"
                elif len(miss) > 2:
                    names = "'" + "', '".join(miss[:-1]) + f"', and '{miss[-1]}'"
                self.err(f"{self.fname(f)}() missing {len(miss)} required {kind} argument{'s' if len(miss) != 1 else ''}: {names}")

    def dispatches(self, f: FnInfo, p: str) -> bool:
        # does template f test its parameter p with isinstance(p, ...), hasattr(p, ...) or p is
        # (not) None, and never assign it: then an object known not to be None decides the tests
        asg: dict[str, bool] = {}
        local_names(f.node.kids[2].kids, asg)
        return p not in asg and self.tests(f.node.kids[2].kids, p)

    def tests(self, ns: list[Node], p: str) -> bool:
        # (see dispatches)
        for n in ns:
            if n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s == "isinstance" or n.kids[0].s == "hasattr") and len(n.kids) == 3 and n.kids[1].kind == "name" and n.kids[1].s == p:
                return True
            if n.kind == "cmp" and (n.s == "is" or n.s == "is not") and n.kids[0].kind == "name" and n.kids[0].s == p and n.kids[1].kind == "None":
                return True
            if self.tests(n.kids, p):
                return True
        return False

    def instance(self, f: FnInfo, ts: list[str], nnp: list[str]) -> FnInfo:
        # the function template f compiles to for arguments of types ts, compiled when first
        # needed, in the middle of the function that calls it: its first return statement
        # decides what it returns; nnp: the parameters whose objects are known not to be None
        key = ",".join(ts) + (" " + ",".join(nnp) if len(nnp) > 0 else "")
        if key in f.insts:
            g = f.insts[key]
            if g.ret == "":
                self.err(f"cannot infer what {short(f.name)}() returns: it calls itself before a return statement does; annotate its return type")
            if g.ll in self.building:
                self.retseen[g.ll] = True  # (a return of None can no longer make it T | None)
            return g
        if f.bad != "":
            self.err(f.bad)
        if len(self.making) >= 100:
            self.err(f"{short(f.name)}() needs more than 100 nested template functions; annotate its parameters")
        g = FnInfo(f.name, f"{f.ll}.{len(f.insts) + 1}", f.node, "")
        g.params = f.params
        g.ptypes = ts
        g.defaults = f.defaults
        g.dglob = f.dglob
        g.dtypes = f.dtypes
        g.uflags = f.uflags
        g.mod = f.mod
        g.ret = f.ret
        g.infer = f.ret == ""
        g.inst = True
        g.npos = f.npos
        g.posonly = f.posonly
        g.vararg = f.vararg
        for x in nnp:
            g.nnp[x] = True
        f.insts[key] = g
        maybe = [f.params[j] for j in range(len(ts)) if ts[j] in self.classes and f.params[j] not in g.nnp and self.dispatches(f, f.params[j])]
        why = f", where {' and '.join(maybe)} may be None: only a new object or self is known not to be None, which decides isinstance(), hasattr() and 'is None' at compile time" if len(maybe) > 0 else ""
        self.making.append(f"compiling {shown(f.name)}({', '.join(ts)}) for the call at {where(self.line)}{why}")
        fr = self.save()
        self.modlevel = False
        self.lenient = False
        self.function(g, f.node.kids[2].kids)
        self.restore(fr)
        self.making.pop()
        return g

    def dotted(self, n: Node) -> str:
        # "sys.argv", "os.path.exists", ... when n is an attribute chain on a module
        if n.kind == "name":
            if n.s in self.aliases and n.s not in self.ltype and n.s not in self.gtypes and n.s not in self.compvars and not self.unbound_local(n.s):
                return self.aliases[n.s]
        elif n.kind == "attr":
            p = self.dotted(n.kids[0])
            if p != "" and p not in MODATTRS:
                return p + "." + n.s
        return ""

    def modattr(self, path: str) -> Val:
        if path == "sys.argv":
            return Val(self.rt("pys_argv", "ptr", []), "list[str]")
        if path == "sys.maxsize":
            return Val("9223372036854775807", "int")
        if path == "sys.stdin" or path == "sys.stdout" or path == "sys.stderr":
            return Val(self.rt("pys_std", "ptr", [f"i64 {0 if path == 'sys.stdin' else 1 if path == 'sys.stdout' else 2}"]), "file")
        if path == "math.pi":
            return Val(fbits("3.141592653589793"), "float")
        if path == "math.e":
            return Val(fbits("2.718281828459045"), "float")
        if path == "math.inf":
            return Val(fbits("inf"), "float")
        if path == "math.tau":
            return Val(fbits("6.283185307179586"), "float")
        if path == "math.nan":
            return Val("0x7FF8000000000000", "float")
        if path == "typing.TYPE_CHECKING":
            return Val("false", "bool")
        if path in OSCONST:
            return Val(self.sconst(OSCONST[path]), "str")
        if path == "sys.platform":
            return Val(self.rt("pys_platform", "ptr", []), "str")
        if path.startswith("errno.") and path[6:] in ERRNO:
            return Val(self.rt("pys_errno", "i64", [f"ptr {self.sconst(path[6:])}"]), "int")
        self.err(f"unsupported module attribute {path}")
        return Val("", "")

    def builtin(self, name: str, args: list[Node], want: str) -> Val:
        if name == "__pys_exc_repr":
            return self.exc_brepr(self.expr(args[0], ""))  # (exc_helpers)
        if name == "__pys_repr_enter" or name == "__pys_repr_leave":
            o = self.expr(args[0], "")
            r = self.rt(name[2:], "i64" if name.endswith("enter") else "void", [f"ptr {o.v}"])
            return Val(self.ins(f"icmp ne i64 {r}, 0"), "bool") if name.endswith("enter") else Val("null", "None")
        if name == "__pys_repr" or name == "__pys_str" or name == "__pys_ascii":
            # compiler-written calls (f"{x!r}", dataclass __repr__): always the builtin
            name = name[6:]
        if name.startswith("builtins."):
            name = name[9:]
        if name == "typing.NamedTuple":
            self.err("the functional NamedTuple form is not supported: write a class, class P(NamedTuple): with annotated fields")
        if "." not in name and name not in PYBUILTINS:
            self.err(f"name '{short(name)}' is not defined")
        # builtins and module functions ("os.system"); most are one call listed in CALLS
        if name == "print":
            return self.print_(args)
        if name == "open":
            return self.open_(args)
        if name == "map" or name == "filter":
            self.err(f"{name}() is not supported; use a list comprehension")
        if name == "format" and 1 <= len(args) <= 2 and len([a for a in args if a.kind == "kw"]) == 0:
            # format(v, spec): what the f-string field {v:spec} gives, v.__format__(spec)
            return self.format_(self.expr(args[0], ""), args[1] if len(args) == 2 else mk("str", "", self.line, []))
        if name == "os.path.join" and len(args) >= 1 and len([a for a in args if a.kind == "kw"]) == 0:
            # posixpath.join: each part after the first is appended with a "/" between them, unless
            # it is absolute (it replaces the path so far) or the path so far is empty or ends in "/"
            pv = self.coerce(self.expr(args[0], "str"), "str", "argument 1 of os.path.join()")
            for k in range(1, len(args)):
                b = self.coerce(self.expr(args[k], "str"), "str", f"argument {k + 1} of os.path.join()")
                pv = Val(self.rt("pys_path_join", "ptr", [f"ptr {pv.v}", f"ptr {b.v}"]), "str")
            return pv
        if name == "hasattr" and len(args) == 2 and args[1].kind == "str":
            # decided by the static type of the object (for an object: is it None)
            hv = self.expr(args[0], "")
            hy = self.has(hv.t, args[1].s)
            if hy == -2:
                # a field that may be unassigned: not None, and its "is assigned" flag
                e0 = self.cur
                l1 = self.label()
                l2 = self.label()
                self.cbr("true" if hv.v in self.nn else self.ins(f"icmp ne ptr {hv.v}, null"), l1, l2)
                self.place(l1)
                fv = self.ins(f"load i1, ptr {self.fgep(hv, self.classes[hv.t].fflag[args[1].s])}")
                e1 = self.cur
                self.br(l2)
                self.place(l2)
                ph = Ins("phi", "bool", "")
                self.incoming(ph, "false", e0)
                self.incoming(ph, fv, e1)
                return Val(self.phi(ph), "bool")
            if hy < 0:
                return Val(self.ins(f"icmp ne ptr {hv.v}, null"), "bool")
            return Val("true" if hy == 1 else "false", "bool")
        if name == "isinstance" and len(args) == 2 and args[0].kind != "kw" and args[1].kind != "kw":
            # decided by the static types, or for an object by whether it is None
            v = self.expr(args[0], "")
            if (v.t == "exc" or (v.t in self.classes and self.classes[v.t].exc != "")) and self.exc_classes(args[1]):
                return self.exc_isinst(v, args[1])
            known = self.isinst(v.t, args[1])
            if known < 0 and ((v.t in self.classes and self.only_class(v.t, args[1])) or (is_opt(v.t) and self.isinst(unopt(v.t), args[1]) == 1)):
                return Val(self.ins(f"icmp ne ptr {v.v}, null"), "bool")
            if known < 0:
                self.err("isinstance() is only supported with the builtin types and classes as its second argument")
            return Val("true" if known == 1 else "false", "bool")
        if (name == "any" or name == "all") and len(args) == 1 and (self.iterator_call(args[0]) or (args[0].kind == "listcomp" and args[0].s == "gen")):
            # these stop at the deciding item, as CPython's iterators do
            g = args[0]
            if g.kind != "listcomp":
                g = mk("listcomp", "gen", g.line, [mk("name", "__item", g.line, []), mk("name", "__item", g.line, []), g])
            return self.listcomp(g, "", name)
        npos = 0
        for a in args:
            if a.kind != "kw":
                npos += 1
            elif name == "sorted" and a.s == "key":
                self.err("sorted(key=...) is not supported: functions are not values")
            elif name != "open" and not (name == "sorted" and a.s == "reverse"):
                self.err(f"keyword argument '{a.s}' of {name}() is not supported")
        if name in ARITY and npos > ARITY[name]:
            m = ARITY[name]
            self.err(f"{name}() takes {'exactly one argument' if m == 1 else f'at most {m} arguments'} ({npos} given)")
        if len(args) == 0 and name in DEFAULTS:
            args = [self.parse_expr(DEFAULTS[name])]
        w = want if name == "list" or name == "sorted" or name == "dict" else ""
        fresh = False
        if npos == 1 and (name == "sorted" or name == "min" or name == "max" or name == "sum" or name == "any" or name == "all" or name == "list"):
            # these iterate their argument at once, so range(), reversed(), enumerate() and zip() may be it
            fresh = self.iterator_call(args[0]) or args[0].kind == "listcomp"
            v0 = self.consume(args[0], w)
            if is_opt(v0.t):
                v0 = self.unwrap(v0, "TypeError: 'NoneType' object is not iterable")
            if name == "any" and v0.t == "file":
                # any(f) reads one line: lines are never empty
                first = self.rt("pys_file_readline", "ptr", [f"ptr {v0.v}"])
                return Val(self.ins(f"icmp ne i64 {self.ins(f'load i64, ptr {first}')}, 0"), "bool")
            vals = [self.as_list(v0, name)]
            self.close_temp(args[0], v0)
        elif name == "sum" and npos == 2 and args[0].kind == "listcomp" and args[0].s == "gen":
            # sum(generator, start): the generator runs once start is evaluated, as in CPython
            st = self.expr(args[1], "")
            vals = [self.consume(args[0], ""), st]
        elif (name == "len" or name == "bool") and len(args) == 1 and args[0].kind == "name" and "?" in self.rtype(args[0].s):
            self.allowq = True
            vals = [self.read(args[0])]
            self.allowq = False
        else:
            vals = [self.expr(a, w) for a in args if a.kind != "kw"]
        rev = "0"
        for a in args:
            if a.kind == "kw" and a.s == "reverse":
                rev = self.reverse_arg(a.kids[0], name)
        if name == "sum" and len(vals) == 2 and vals[1].t == "bool":
            vals[1] = self.as_int(vals[1])
        if name == "sum" and len(vals) == 2 and (vals[0].t in self.classes or is_tuple(vals[0].t) or is_dict(vals[0].t)):
            vals[0] = self.as_list(vals[0], "sum")  # (sum(o, start) iterates o once start is evaluated)
        if name == "round" and len(vals) == 2 and vals[1].t == "None":
            vals = vals[:1]  # round(x, None) is round(x)
        elif name == "round" and len(vals) == 2 and is_sopt(vals[1].t) and (unopt(vals[0].t) == "int" or unopt(vals[0].t) == "bool"):
            # an ndigits that may be None: for an int, round(x, None) is round(x, 0)
            vals[1] = self.coerce(Val(self.optint(vals[1], "0"), "int"), "int")
        elif name == "round" and len(vals) == 2 and is_opt(vals[1].t):
            self.err(f"round() with an ndigits that may be None ({typestr(vals[1].t)}) is not supported: it returns an int where ndigits is None, else a float; test it with 'is not None' first")
        for i in range(len(vals)):
            if vals[i].t == "None" and name in NONERET and len(vals) == 1:
                # None itself (a template's parameter whose argument is None): CPython's error
                self.raise_("TypeError", self.sconst(NONEARG[name]))
                return Val("0" if NONERET[name] == "int" else "false" if NONERET[name] == "bool" else fbits("0.0"), NONERET[name])
            if not is_opt(vals[i].t):
                continue
            bad = NONEARG[name] if name in NONEARG else ""
            if name == "int" and len(vals) == 2:
                bad = "int() can't convert non-string with explicit base"
            elif name == "sum" and i == 0:
                bad = "'NoneType' object is not iterable"
            if bad != "":
                vals[i] = self.unwrap(vals[i], "TypeError: " + bad)
            elif name not in OPTARG:
                if f"{name}({','.join([unopt(v.t) for v in vals])})" not in CALLS and name not in OPTCALLS:
                    # (not for the value it holds either)
                    self.err(f"unsupported call {name}({','.join([typestr(v.t) for v in vals])})")
                self.err(f"argument {i + 1} of {name}() may be None ({typestr(vals[i].t)}); test it with 'is not None' first")
        key = f"{name}({','.join([v.t for v in vals])})"
        if key in DEFAULTS:
            vals.append(self.expr(self.parse_expr(DEFAULTS[key]), ""))
            key = f"{name}({','.join([v.t for v in vals])})"
        if name == "input" and len(vals) == 1 and vals[0].t != "str":
            vals[0] = self.to_str(vals[0])
            key = "input(str)"
        if name == "input" and len(vals) == 0:
            # no prompt: CPython writes nothing to sys.stdout (which may be closed) before reading
            return Val(self.rt("pys_input", "ptr", ["ptr null"]), "str")
        if name == "sys.exit" or name == "exit" or name == "quit":
            if len(vals) > 1:
                self.err(f"sys.exit() takes at most 1 argument ({len(vals)} given)")
            if len(vals) == 1 and vals[0].t in self.classes and self.derives(vals[0].t, "SystemExit"):
                self.throw(self.exc_of(vals[0]))  # (a SystemExit itself is raised as it is)
                return Val("null", "None")
            self.exit_(vals if len(vals) == 0 or vals[0].t != "None" else [])
            return Val("null", "None")
        if name == "os.fspath" and len(vals) == 1 and vals[0].t == "str":
            return vals[0]  # a str path is its own file system path
        if name == "os.getenv" and (len(vals) == 1 or (len(vals) == 2 and vals[1].t == "None")):
            # without a default the result is the variable's value or None
            return Val(self.rt("pys_getenv", "ptr", [f"ptr {self.coerce(vals[0], 'str', 'argument 1 of os.getenv()').v}", "ptr null"]), "opt[str]")
        if (name == "math.floor" or name == "math.ceil" or name == "math.trunc") and len(vals) == 1 and (vals[0].t == "int" or vals[0].t == "bool"):
            return self.as_int(vals[0])
        if name == "round" and len(vals) >= 1 and (vals[0].t == "int" or vals[0].t == "bool"):
            # an int's round(x) is x, and round(x, n) rounds it to a multiple of 10**-n for n < 0
            if len(vals) == 1:
                return self.as_int(vals[0])
            nd = self.coerce(self.as_int(vals[1]), "int")
            return Val(self.rt("pys_round_int", "i64", [f"i64 {self.as_int(vals[0]).v}", f"i64 {nd.v}"]), "int")
        if key not in CALLS and name == "math.ldexp" and len(vals) == 2:
            vals = [self.as_float(self.as_int(vals[0])), self.as_int(vals[1])]
            key = f"{name}({','.join([v.t for v in vals])})"
        if key not in CALLS and name.startswith("math."):
            vals = [self.as_float(v) for v in vals]
            key = f"{name}({','.join([v.t for v in vals])})"
        if (name == "any" or name == "all") and len(vals) == 1 and is_list(vals[0].t) and key not in CALLS:
            return self.anyall(vals[0], name)
        if key in CALLS:
            spec = CALLS[key].split(":")
            r = spec[1] if spec[1] != "" else vals[0].t
            return self.rres(self.rt(spec[0], rtt(r), [self.rarg(v) for v in vals]), r)
        if len(vals) == 0:
            self.err(f"unsupported call {name}()")
        v = vals[0]
        t = v.t
        if name == "len":
            if t in self.classes and "__len__" in self.classes[t].methods:
                self.notnone(v, "TypeError: object of type 'NoneType' has no len()")
                return self.objlen(v)
            if t in self.nts:
                self.notnone(v, "TypeError: object of type 'NoneType' has no len()")
                return Val(str(len(self.classes[t].fields)), "int")
            if t == "str" or is_list(t) or is_dict(t):
                return Val(self.ins(f"load i64, ptr {v.v}"), "int")
            if is_tuple(t):
                return Val(str(len(targs(t))), "int")
        elif name == "str":
            return self.to_str(v)
        elif name == "repr":
            return self.repr(v)
        elif name == "ascii":
            return Val(self.rt("pys_ascii", "ptr", [f"ptr {self.repr(v).v}"]), "str")
        elif name == "bool":
            return Val(self.truth(v), "bool")
        elif name == "int" and (t == "int" or t == "bool"):
            return self.as_int(v)
        elif name == "float" and (t == "float" or t == "int" or t == "bool"):
            return self.as_float(v)
        elif name == "abs" and (t == "int" or t == "bool"):
            v = self.as_int(v)
            c = self.ins(f"icmp slt i64 {v.v}, 0")
            neg = self.iop("-", "0", v.v)
            return Val(self.select(c, Val(neg, "int"), v), "int")
        elif (name == "min" or name == "max") and len(vals) == 1 and is_list(t):
            d = self.sconst(self.desc(elem(t), ">" if name == "max" else "<"))
            r = self.rt("pys_list_minmax", "i64", [f"ptr {v.v}", f"ptr {d}", f"i64 {1 if name == 'max' else 0}"])
            return self.from_slot(r, elem(t))
        elif (name == "min" or name == "max") and len(vals) == 1:
            self.err(f"'{tname(t)}' object is not iterable")
        elif name == "min" or name == "max":
            for b in vals[1:]:
                t = t if self.join(t, b.t) == "" else self.join(t, b.t)  # (T and T | None: the comparison raises for None)
            v = self.coerce(v, t)
            for b in vals[1:]:
                b = self.coerce(b, t)
                gt = self.cmp2(">" if name == "max" else "<", b, v)
                v = Val(self.select(gt.v, Val(b.v, t), Val(v.v, t)), t)
            return v
        elif (name == "sorted" or name == "list") and is_list(t):
            c = v.v if fresh else self.rt("pys_list_copy", "ptr", [f"ptr {v.v}"])
            if name == "sorted":
                self.rt("pys_list_sort_r", "void", [f"ptr {c}", f"ptr {self.sconst(self.desc(elem(t), '<'))}", f"i64 {rev}"])
            return Val(c, t)
        elif name == "divmod" and len(vals) == 2 and self.isnum(t) and self.isnum(vals[1].t):
            dn = self.as_int(v)
            dd = self.as_int(vals[1])
            if dn.t == "int" and dd.t == "int":
                return self.tuple_([self.arith("//", dn, dd), self.arith("%", dn, dd)])
            dn = self.as_float(dn)
            dd = self.as_float(dd)
            self.guard(self.ins(f"fcmp oeq double {dd.v}, 0.0"), "ZeroDivisionError: float divmod()")
            return self.tuple_([self.arith("//", dn, dd), self.arith("%", dn, dd)])
        elif name == "pow" and len(vals) == 2:
            return self.arith("**", v, vals[1])
        elif name == "pow" and len(vals) == 3 and self.as_int(v).t == "int":
            pm = [self.coerce(self.as_int(x), "int").v for x in vals]
            return Val(self.rt("pys_powmod", "i64", [f"i64 {pm[0]}", f"i64 {pm[1]}", f"i64 {pm[2]}"]), "int")
        elif name == "dict" and is_dict(t):
            # not d.copy(): dict(d) merges d into an empty dict, whose table can differ (runtime.c)
            return Val(self.rt("pys_dict_from", "ptr", [f"ptr {v.v}"]), t)
        elif name == "list" and is_dict(t):
            return Val(self.rt("pys_dict_keys", "ptr", [f"ptr {v.v}"]), f"list[{targs(t)[0]}]")
        elif name == "range" or name == "enumerate" or name == "zip" or name == "reversed":
            self.err(f"{name}() is only supported in a for loop, after 'in', or as the argument of list(), sorted(), sum(), min(), max(), any(), all() or str.join()")
        if name in self.gtypes or name in self.ltype:
            self.err(f"'{name}' is not callable")
        if t in self.classes and name in NONEARG:
            self.err(NONEARG[name].replace("NoneType", tname(t)))  # (CPython's TypeError: its class has no __len__, __abs__, ...)
        if name == "type" and len(vals) == 1 and (t == "exc" or (t in self.classes and self.classes[t].exc != "")):
            self.err(f"unsupported call {key}: type(e) of an exception is supported as type(e).__name__ (and isinstance(e, C) tests its class)")
        self.err(f"unsupported call {key}")
        return v

    def anyall(self, v: Val, name: str) -> Val:
        # any(xs) / all(xs) by each item's truth, stopping at the first item that decides
        res = self.alloca("bool", "")
        self.emit(f"store i1 {'false' if name == 'any' else 'true'}, ptr {res}")
        ctr = self.alloca("int", "")
        self.emit(f"store i64 0, ptr {ctr}")
        lc = self.label()
        lb = self.label()
        hit = self.label()
        ls = self.label()
        le = self.label()
        lp = Loop("seq", lc, lb, ls, le)
        lp.seqs = [v]
        lp.tests = [lb]
        lp.ctr = ctr
        self.fn.loops.append(lp)
        self.place(lc)
        i = self.ins(f"load i64, ptr {ctr}")
        lp.idx = [i]
        self.cbr(self.ins(f"icmp slt i64 {i}, {self.ins(f'load i64, ptr {v.v}')}"), lb, le)
        self.place(lb)
        c = self.truth(self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {v.v}", f"i64 {i}"]), elem(v.t)))
        if name == "any":
            self.cbr(c, hit, ls)
        else:
            self.cbr(c, ls, hit)
        self.place(hit)
        self.emit(f"store i1 {'true' if name == 'any' else 'false'}, ptr {res}")
        self.br(le)
        self.place(ls)
        self.emit(f"store i64 {self.ins(f'add i64 {i}, 1')}, ptr {ctr}")
        self.br(lc)
        self.place(le)
        return Val(self.ins(f"load i1, ptr {res}"), "bool")

    def iterator_call(self, n: Node) -> bool:
        if n.kind != "call" or n.kids[0].kind != "name" or self.bound(n.kids[0].s):
            return False
        fn = n.kids[0].s
        return fn == "range" or fn == "reversed" or fn == "enumerate" or fn == "zip"

    def consume(self, n: Node, want: str) -> Val:
        # range(), reversed(), enumerate(), zip() and generator expressions where their items are
        # used at once (list(), sorted(), "".join(), ...) become a fresh list of those items, built
        # by the for loop machinery; anywhere else they are rejected, as a list would behave differently
        if n.kind == "listcomp":
            return self.listcomp(n, want)
        if not self.iterator_call(n):
            return self.expr(n, want)
        if n.kids[0].s == "range":
            vs = self.range_args(n.kids[1:])
            return Val(self.rt("pys_range_list", "ptr", [f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"]), "list[int]")
        it = mk("name", "__item", n.line, [])
        return self.listcomp(mk("listcomp", "", n.line, [it, mk("name", "__item", n.line, []), n]), want)

    def as_list(self, v: Val, name: str) -> Val:
        # sorted(d), max(t), ...: a dict's keys, or the items of a tuple (or NamedTuple) of one item
        # type, as a list, or the list an object's __iter__ steps through (which list() copies)
        if v.t in self.nts:
            self.notnone(v, "TypeError: 'NoneType' object is not iterable")
            v = self.ntup(v, True)
        if v.t in self.classes:
            items = self.obj_iter(v, "TypeError: can only join an iterable" if name == "join" else "TypeError: 'NoneType' object is not iterable",
                                  "can only join an iterable" if name == "join" else f"'{tname(v.t)}' object is not iterable")
            if (name == "list" or name == "sorted" or name == "extend") and "__len__" in self.classes[v.t].methods:
                self.objlen(v)  # (a length hint: CPython's list() calls __len__ once __iter__ has run)
            return items
        if is_dict(v.t):
            return Val(self.rt("pys_dict_keys", "ptr", [f"ptr {v.v}"]), f"list[{targs(v.t)[0]}]")
        if is_tuple(v.t):
            ts = targs(v.t)
            for x in ts:
                if x != ts[0]:
                    self.err(f"{name}() of a {v.t} needs items of a single type")
            r = self.rt("pys_list_new", "ptr", [f"i64 {len(ts)}"])
            for i in range(len(ts)):
                self.rt("pys_list_append", "void", [f"ptr {r}", "i64 " + self.to_slot(self.tget(v, i))])
            return Val(r, f"list[{ts[0]}]")
        if v.t == "str" and (name == "sorted" or name == "min" or name == "max" or name == "join"):
            return Val(self.rt("pys_str_list", "ptr", [f"ptr {v.v}"]), "list[str]")
        if v.t == "file":
            return Val(self.rt("pys_file_readlines", "ptr", [f"ptr {v.v}"]), "list[str]")
        return v

    def reverse_arg(self, n: Node, name: str) -> str:
        # sorted(..., reverse=r) and list.sort(reverse=r): r is a bool or an int, as in CPython
        r = self.expr(n, "bool")
        if r.t != "bool" and r.t != "int":
            self.err(f"{name}() argument 'reverse' must be a bool, not {tname(r.t)}")
        return self.ins(f"zext i1 {self.truth(r)} to i64")

    def parse_expr(self, text: str) -> Node:
        return Parser(Lexer(text, self.line).run()).test()

    def print_(self, args: list[Node]) -> Val:
        # every argument is evaluated in the order written, then each is converted as it is
        # written; sys.stdout and sys.stderr directly, any other file through its checks
        sep = self.sconst(" ")
        end = self.sconst("\n")
        fd = "1"
        fv = ""
        flush = ""
        vals: list[Val] = []
        temp: list[Node] = []  # file=open(...): closed after the print, as close_temp does
        for a in args:
            if a.kind != "kw":
                vals.append(self.expr(a, ""))
                continue
            x = a.kids[0]
            if a.s == "sep" or a.s == "end":
                if x.kind != "None":
                    v = self.expr(x, "str")
                    if is_opt(v.t):
                        # None is the default
                        v = Val(self.select(self.isnull(v), Val(sep if a.s == "sep" else end, "str"), Val(v.v, "str")), "str")
                    sv = self.coerce(v, "str").v
                    if a.s == "sep":
                        sep = sv
                    else:
                        end = sv
            elif a.s == "file":
                p = self.dotted(x)
                if p == "sys.stdout" or p == "sys.stderr":
                    fd = "2" if p == "sys.stderr" else "1"
                elif x.kind != "None":
                    v = self.expr(x, "file")
                    if v.t != "file":
                        self.err(f"print(file=...) needs a file, not {v.t}")
                    fv = v.v
                    temp.append(x)
            elif a.s == "flush":
                flush = self.truth(self.expr(x, "bool"))
            else:
                self.err(f"print() got an unexpected keyword argument '{a.s}'")
        for i in range(len(vals)):
            if i > 0:
                self.pwrite(fd, fv, sep)
            self.pwrite(fd, fv, self.to_str(vals[i]).v)
        self.pwrite(fd, fv, end)
        if flush != "":
            l1 = self.label()
            l2 = self.label()
            self.cbr(flush, l1, l2)
            self.place(l1)
            self.rt("pys_file_flush", "void", [f"ptr {fv if fv != '' else self.rt('pys_std', 'ptr', [f'i64 {fd}'])}"])
            self.br(l2)
            self.place(l2)
        for x in temp:
            self.close_temp(x, Val(fv, "file"))
        return Val("null", "None")

    def pwrite(self, fd: str, fv: str, s: str) -> None:
        if fv != "":
            self.rt("pys_file_write", "i64", [f"ptr {fv}", f"ptr {s}"])
        else:
            self.rt("pys_write", "void", [f"ptr {s}", f"i64 {fd}"])

    def bmethod(self, o: Val, m: str, args: list[Node]) -> Val:
        if is_list(o.t) and m == "sort":
            rev = "0"
            for a in args:
                if a.kind != "kw":
                    self.err("list.sort() takes no positional arguments")
                elif a.s == "reverse":
                    rev = self.reverse_arg(a.kids[0], "sort")
                else:
                    self.err(f"list.sort({a.s}=...) is not supported" if a.s == "key" else f"sort() got an unexpected keyword argument '{a.s}'")
            self.rt("pys_list_sort_r", "void", [f"ptr {o.v}", f"ptr {self.sconst(self.desc(elem(o.t), '<'))}", f"i64 {rev}"])
            return Val("null", "None")
        for a in args:
            if a.kind == "kw":
                self.err(f"keyword arguments to {tname(o.t)}.{m}() are not supported; pass them by position")
        if is_list(o.t) and m == "extend" and len(args) == 1 and args[0].kind == "listcomp" and args[0].s == "gen":
            # each item is appended as the generator yields it: the items before a raise stay, and
            # the generator sees those it added (xs.extend(f(x) for x in xs))
            self.listcomp(args[0], o.t, "", o.v)
            return Val("null", "None")
        if is_dict(o.t) and m == "pop" and len(args) == 2:
            kv = targs(o.t)
            kx = self.dkey(self.expr(args[0], kv[0]), kv[0])
            k = self.to_slot(kx)
            d = self.expr(args[1], kv[1])
            vt = self.optdefault(d, kv[1])  # (d.pop(k, None): V | None)
            dv = self.to_slot(self.coerce(d, vt))
            fn = "pys_dict_popbox" if is_sopt(vt) and not is_sopt(kv[1]) else "pys_dict_pop_default"  # (an int's box)
            return self.from_slot(self.nonekey(kx, dv, fn, [f"ptr {o.v}", f"i64 {k}", f"i64 {dv}"]), vt)
        base = o.t
        T = ""
        K = ""
        V = ""
        if is_list(o.t):
            base = "list"
            T = elem(o.t)
        elif is_dict(o.t):
            base = "dict"
            kv = targs(o.t)
            K = kv[0]
            V = kv[1]
        key = base + "." + m
        if key not in METHODS and o.t == "exc":
            self.err(f"BaseException.{m}() is not supported (of a builtin exception, str(e), repr(e) and formatting are)")
        if key not in METHODS:
            self.err(f"'{o.t}' has no method '{m}'")
        # d.get(k) and d.get(k, None): the value or None, for values that can be None
        optget = key == "dict.get" and (len(args) == 1 or args[-1].kind == "None") and V not in self.classes and self.optional(V) != ""
        if optget:
            args = args[:1]
        if key == "dict.get" and (len(args) == 1 or args[-1].kind == "None") and V not in self.classes and not optget:
            self.err(f"dict.get(key{', None' if len(args) == 2 else ''}) needs values that can be None ({OPTTYPES}), not {typestr(V)}: give another default")
        spec = METHODS[key]
        c = spec.find(":")
        av = [f"{lt(o.t)} {o.v}"]
        nones: list[str] = []  # optional str arguments: None raises (nmsg) once all are evaluated
        nmsg: list[str] = []
        dt = T  # the item type the # descriptor describes
        kx = Val("", "")  # a dict's key that may be None (see nonekey)
        bk = Val("", "")  # d.pop(k) of a bool where the keys are ints (bool_find)
        numx = Val("", "")  # xs.index(x), count(x) or remove(x) of a number x of another type
        numok = "true"  # (whether an item can equal it, see numkey)
        i = 0
        for p in spec[c + 1 :].split(","):
            if p == "":
                continue
            if p == "#":
                self.exc_eq(dt)
                av.append(f"ptr {self.sconst(self.desc(dt, '=='))}")  # (count, index, remove)
                continue
            dflt = ""
            e = p.find("=")
            if e >= 0:
                dflt = p[e + 1 :]
                p = p[:e]
            slot = p.startswith("*")
            pt = subst(p[1:] if slot else p, T, K, V, o.t)
            # a str method's start or end (find, count, startswith, ...) that is None is omitted
            span = base == "str" and p == "int" and (dflt == "0" or dflt == "9223372036854775807")
            if i < len(args) and dflt == "null" and args[i].kind == "None":
                av.append(rtt(pt) + " null")  # an explicit None: the default
            elif i < len(args) and span and args[i].kind == "None":
                av.append("i64 " + dflt)
            elif i < len(args):
                v = self.consume(args[i], pt) if key == "str.join" or key == "list.extend" else self.expr(args[i], pt)
                if is_opt(v.t) and (key == "str.join" or key == "list.extend" or key == "file.writelines"):
                    v = self.unwrap(v, "TypeError: can only join an iterable" if key == "str.join" else "TypeError: 'NoneType' object is not iterable")
                if key == "str.join" or (key == "list.extend" and v.t in self.classes):
                    v = self.as_list(v, "join" if key == "str.join" else "extend")
                if (key == "str.join" or key == "file.writelines") and v.t == "list[opt[str]]":
                    v = Val(v.v, "list[str]")  # (an item that is None raises when it runs, as CPython's error)
                if key == "str.join" and is_list(v.t) and elem(v.t) != "str" and "?" not in v.t:
                    self.err(f"sequence item 0: expected str instance, {tname(elem(v.t))} found")  # (CPython's TypeError)
                if key == "list.extend" and is_list(v.t) and v.t != pt and self.wider(v.t, pt) == pt:
                    v = Val(v.v, pt)  # (its items are copied: list[str] extends a list[str | None])
                if span and is_sopt(v.t) and unopt(v.t) != "float":
                    v = Val(self.optint(v, dflt), "int")
                if p == "int":
                    v = self.as_int(v)  # an index or a count may be a bool, as in CPython
                if base == "dict" and i == 0 and is_opt(v.t) and unopt(v.t) == K and (m == "get" or m == "pop"):
                    kx = v
                    pt = v.t
                elif base == "dict" and i == 0 and (m == "get" or m == "pop"):
                    if m == "pop" and bool_for_int(v.t, K):
                        bk = v
                    v = self.dkey(v, K)
                elif key == "dict.setdefault" and i == 0 and bool_for_int(v.t, K):
                    self.store_key(v, K)  # (rejected)
                elif key == "dict.get" and i == 1 and self.optdefault(v, V) != V:
                    pt = self.optdefault(v, V)  # d.get(k, default) with a default that may be None: V | None
                    optget = True
                if base == "list" and p == "*T" and self.isnum(v.t) and self.isnum(unopt(T)) and v.t != unopt(T) and (m == "index" or m == "count" or m == "remove"):
                    numx = v
                    nk = self.numkey(v, unopt(T))
                    v = Val(nk[0], unopt(T))
                    numok = nk[1]
                if is_opt(v.t) and unopt(v.t) == pt and dflt == "null":
                    v = Val(v.v, pt)  # None is the default
                elif is_opt(v.t) and not slot and unopt(v.t) == pt == "str":
                    nones.append(v.v)
                    nmsg.append(self.none_arg(m, i + 1))
                    v = Val(v.v, pt)
                elif (is_opt(v.t) or v.t == "None") and slot and p == "*T" and (unopt(v.t) == T or (v.t == "None" and T not in self.classes)) and base == "list" and m != "append" and m != "insert" and self.optional(T) != "" and not self.isnum(T):
                    pt = self.optional(T)  # xs.index(None): found where xs holds None, as == finds it
                    dt = pt
                v = self.coerce(v, pt, f"argument {i + 1} of {tname(o.t)}.{m}()" if is_opt(v.t) else "")
                av.append("i64 " + self.to_slot(v) if slot else self.rarg(v))
            elif dflt != "":
                av.append(("i64 " if slot else rtt(pt) + " ") + dflt)
            else:
                self.err(f"missing argument for {m}()")
            i += 1
        if i < len(args):
            self.err(f"too many arguments for {m}()")
        for j in range(len(nones)):
            self.guard(self.ins(f"icmp eq ptr {nones[j]}, null"), nmsg[j])
        r = spec[:c]
        slot = r.startswith("*")
        rtype = subst(r[1:] if slot else r, T, K, V, o.t)
        if optget:
            rtype = self.optional(V)
        fn = f"pys_{base}_{m}"
        if optget and is_sopt(rtype) and not is_sopt(V):
            fn = "pys_dict_getbox"  # (the value's box: an int | None)
        if numok != "true" and m == "remove":
            self.guard(self.ins(f"xor i1 {numok}, true"), "ValueError: list.remove(x): x not in list")
        if numx.t != "" and m == "index":
            fn = "pys_list_index_as"  # (its ValueError names x, not the item)
            av = av + ["i64 " + self.to_slot(Val(numok, "bool")), "i64 " + self.to_slot(numx), f"ptr {self.sconst(self.desc(numx.t, '=='))}"]
        if bk.t != "":
            self.bool_find(o.v, bk, av[1][4:])
        if kx.t != "":
            res = self.nonekey(kx, av[2][4:] if m == "get" else "", fn, av)
        else:
            res = self.rt(fn, "i64" if slot else rtt(rtype), av)
        if numok != "true" and m == "count":
            res = self.select(numok, Val(res, "int"), Val("0", "int"))
        if slot:
            return self.from_slot(res, rtype)
        return self.rres(res, rtype)

    def optdefault(self, d: Val, t: str) -> str:
        # the type of d.get(k, d) and d.pop(k, d) for values of type t: t | None for a default
        # that may be None
        if (d.t == "None" or (is_opt(d.t) and unopt(d.t) == t)) and t not in self.classes and self.optional(t) != "":
            return self.optional(t)
        return t

    def key_kind(self, kt: str) -> str:
        # the key kind of a new dict whose keys have type kt (runtime.c's Dict.kind): 0 int, 1 str,
        # or a tuple key's type descriptor
        if kt == "int" or kt == "str":
            return "1" if kt == "str" else "0"
        return f"ptrtoint (ptr {self.sconst(self.desc(kt, '=='))} to i64)"

    def dkey(self, k: Val, kt: str) -> Val:
        # a key to look up in a dict whose keys have type kt: one that may be None stays optional
        # (see nonekey), and a bool or a tuple with what CPython finds as such a key (lookable) is one
        if is_opt(k.t) and unopt(k.t) == kt:
            return k
        if k.t == "bool" and kt == "int":
            return self.as_int(k)  # (True is the key 1)
        if is_tuple(k.t) and k.t != kt and lookable(k.t, kt):
            return Val(k.v, kt)  # (a None where the keys hold a str finds none: runtime.c's hval)
        return self.coerce(k, kt)

    def bool_find(self, d: str, k: Val, key: str) -> str:
        # the entry of key k in dict d (key: k's slot as a key of d's type), where k holds a bool
        # and d's keys an int (bool_for_int): one that d does not hold raises CPython's KeyError
        # here, naming k as it is (KeyError: True), where the runtime's lookup would name the key
        # as the int it equals (KeyError: 1)
        e = self.rt("pys_dict_find", "i64", [f"ptr {d}", f"i64 {key}"])
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.ins(f"icmp slt i64 {e}, 0"), l1, l2)
        self.place(l1)
        self.raise_("KeyError", self.repr(k).v)
        self.place(l2)
        return e

    def store_key(self, k: Val, kt: str) -> Val:
        # k as a key stored into a dict whose keys have type kt (d[k] = v, d[k] op= v, a display,
        # setdefault): a bool is rejected where the keys hold an int, as it is where an int is
        # stored, since CPython keeps a key it adds as it is, which prints as True, not 1 (it
        # looks up, pops and deletes the int key it equals: dkey)
        if bool_for_int(k.t, kt):
            self.err(f"a {typestr(k.t)} key is stored into a dict with {typestr(kt)} keys, where CPython keeps a key it adds as the bool it is (True, not 1): convert the bool with int()")
        return self.coerce(k, kt)

    def nonekey(self, k: Val, none: str, fn: str, av: list[str]) -> str:
        # the slot fn(av) returns, a dict lookup of key k; a key that is None is in no dict: the
        # result is then the slot none, or with none "" KeyError: None
        if not is_opt(k.t):
            return self.rt(fn, "i64", av)
        if none == "":
            self.guard(self.ins(f"icmp eq ptr {k.v}, null"), "KeyError: None")
            return self.rt(fn, "i64", self.keyed(k, av))
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(self.ins(f"icmp eq ptr {k.v}, null"), l1, l2)
        self.place(l2)
        r = self.rt(fn, "i64", self.keyed(k, av))
        e2 = self.cur
        self.br(l3)
        self.place(l1)
        self.br(l3)
        self.place(l3)
        ph = Ins("phi", "%slot", "")
        self.incoming(ph, none, l1)
        self.incoming(ph, r, e2)
        return self.phi(ph)

    def keyed(self, k: Val, av: list[str]) -> list[str]:
        # the arguments av of a dict lookup by key k (av[1]), which is not None here: an int key
        # that may be None is the int its box holds
        if not is_sopt(k.t):
            return av
        return [av[0], "i64 " + self.to_slot(self.deref(k))] + av[2:]

    def none_arg(self, m: str, k: int) -> str:
        # what str method m (or file.write) raises for None as its argument k
        if m == "startswith" or m == "endswith":
            return f"TypeError: {m} first arg must be str or a tuple of str, not NoneType"
        if m == "partition" or m == "rpartition":
            return "TypeError: must be str, not NoneType"
        if m == "removeprefix" or m == "removesuffix" or m == "write":
            return f"TypeError: {m}() argument must be str, not None"
        return f"TypeError: {m}() argument {k} must be str, not None"

    def to_str(self, v: Val) -> Val:
        t = v.t
        if t == "str":
            return v
        if t == "int":
            return Val(self.rt("pys_str_int", "ptr", [f"i64 {v.v}"]), "str")
        if t == "float":
            return Val(self.rt("pys_str_float", "ptr", [f"double {v.v}"]), "str")
        if t == "bool":
            return Val(self.select(v.v, Val(self.sconst("True"), "str"), Val(self.sconst("False"), "str")), "str")
        if t == "None":
            return Val(self.sconst("None"), "str")
        if t in self.classes:
            return self.obj_str(v, "__str__")
        if t == "opt[str]":
            return Val(self.select(self.ins(f"icmp eq ptr {v.v}, null"), Val(self.sconst("None"), "str"), Val(v.v, "str")), "str")
        if t == "exc":
            return Val(self.rt("pys_exc_str", "ptr", [f"ptr {v.v}"]), "str")
        return self.repr(v)

    def obj_str(self, v: Val, m: str) -> Val:
        # str()/repr() of an object through __str__/__repr__; None prints as "None". An exception
        # object's are those of its class (its ExcClass's: exc_helpers)
        ms = self.classes[v.t].methods
        exc = self.classes[v.t].exc != ""
        if m not in ms and not exc:
            m = "__repr__"
        if m in ms and ms[m].bad != "" and self.lenient:
            m = ""  # (see desc)
        if v.v in self.nn and exc:
            return Val(self.rt("pys_exc_ostr" if m == "__str__" else "pys_exc_orepr", "ptr", [f"ptr {v.v}"]), "str")
        if v.v in self.nn and m in ms:
            return self.call_fn(ms[m], [v], [])
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(self.ins(f"icmp eq ptr {v.v}, null"), l1, l2)
        self.place(l1)
        self.br(l3)
        self.place(l2)
        if exc:
            r = Val(self.rt("pys_exc_ostr" if m == "__str__" else "pys_exc_orepr", "ptr", [f"ptr {v.v}"]), "str")
        elif m in ms:
            r = self.call_fn(ms[m], [v], [])
        else:
            # object.__repr__: <__main__.Name object at 0x...>, <module.Name object at 0x...>
            qn = shown(v.t) if "$" in v.t and not v.t.startswith("__main__$") else "__main__." + short(v.t)
            r = Val(self.rt("pys_default_repr", "ptr", [f"ptr {self.sconst(qn)}", f"ptr {v.v}"]), "str")
        e2 = self.cur
        self.br(l3)
        self.place(l3)
        ph = Ins("phi", "str", "")
        self.incoming(ph, self.sconst("None"), l1)
        self.incoming(ph, r.v, e2)
        return Val(self.phi(ph), "str")

    def repr(self, v: Val) -> Val:
        if v.t in self.classes:
            return self.obj_str(v, "__repr__")
        if v.t == "None":
            return Val(self.sconst("None"), "str")
        if v.t == "file":
            self.err(f"cannot convert {v.t} to str")
        if v.t == "exc":
            return Val(self.rt("pys_exc_repr", "ptr", [f"ptr {v.v}"]), "str")
        return Val(self.rt("pys_repr", "ptr", ["i64 " + self.to_slot(v), f"ptr {self.sconst(self.desc(v.t, 'repr'))}"]), "str")


# ---------------------------------------------------------------- driver
def compile_program(path: str, src: str, dirs: list[str]) -> str:
    return Gen().program(Loader(dirs).program(path, src))


def q(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def sh(cmd: str) -> int:
    st = os.system(cmd)
    return st >> 8 if st & 255 == 0 else 1


def main() -> None:
    global SRC
    # the parser and the code generator recurse for each level of nesting (at most MAXNEST), a
    # dozen calls deep each: more than CPython's default limit of 1,000 calls when it runs this file
    sys.setrecursionlimit(MAXNEST * 40)
    argv = sys.argv
    if len(argv) < 3 or (argv[1] != "run" and argv[1] != "build" and argv[1] != "ir" and argv[1] != "check"):
        print("usage: pystachy run FILE.py [ARGS...]   JIT-compile and run (LLVM ORC via lli)", file=sys.stderr)
        print("       pystachy build FILE.py [-o EXE]  compile ahead of time to a native executable", file=sys.stderr)
        print("       pystachy ir FILE.py [-o OUT.ll]  emit LLVM IR", file=sys.stderr)
        print("       pystachy check FILE.py           only parse it, with the checks CPython makes before running it", file=sys.stderr)
        sys.exit(2)
    cmd = argv[1]
    SRC = argv[2]
    if not os.path.exists(SRC):
        fail("file not found", 0)
    if cmd == "check":
        f = open(SRC, "r", encoding="latin-1")
        Parser(Lexer(f.read(), 1).file()).module()
        f.close()
        return
    home = os.getenv("PYSTACHY_HOME", "")
    if home == "":
        s = argv[0].rfind("/")
        home = argv[0][:s] if s >= 0 else "."
        if not os.path.exists(home + "/runtime.c"):
            home = home + "/.."
    # where imported modules are found: the directory of the program's real path (symbolic links
    # resolved, as CPython's sys.path[0]; spelled as given where that is the same), PYSTACHY_PATH,
    # lib/ of the checkout
    s = SRC.rfind("/")
    d = SRC[:s] if s > 0 else "/" if s == 0 else "."
    real = os.path.realpath(SRC)
    if os.path.realpath(d).rstrip("/") + "/" + SRC[s + 1 :] != real:
        d = real[: real.rfind("/")] if real.rfind("/") > 0 else "/"
    dirs = [d]
    for d in os.getenv("PYSTACHY_PATH", "").split(":"):
        if d != "":
            dirs.append(d)
    dirs.append(home + "/lib")
    f = open(SRC, "r", encoding="latin-1")
    ir = compile_program(SRC, f.read(), dirs)
    f.close()
    out = ""
    rest: list[str] = []
    i = 3
    while i < len(argv):
        if argv[i] == "-o" and i + 1 < len(argv) and cmd != "run":
            out = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    if cmd == "ir":
        if out == "":
            print(ir, end="")
        else:
            f = open(out, "w", encoding="latin-1")
            f.write(ir)
            f.close()
        return
    rtc = home + "/runtime.c"
    if not os.path.exists(rtc):
        fail("cannot find runtime.c next to the compiler; set PYSTACHY_HOME to the directory that holds it", 0)
    # PYSTACHY_CFLAGS: extra clang flags (e.g. -fsanitize=undefined) for the runtime and the AOT link.
    # The runtime is compiled with them and then -fexceptions (so they cannot drop it): a raise unwinds
    # through runtime functions to compiled code's landing pads, which -O2 would turn back into calls
    # if clang marked them nounwind. Each such set of flags caches its own runtime, named by a 32-bit
    # FNV-1a hash of it, so a runtime cached without -fexceptions is never used
    flags = os.getenv("PYSTACHY_CFLAGS", "").split()
    key = 2166136261
    for c in " ".join(flags + ["-fexceptions"]):
        key = ((key ^ ord(c)) * 16777619) & 0xFFFFFFFF
    rtb = home + f"/build/runtime-{key:08x}.bc"
    cflags = "".join([" " + q(a) for a in flags])
    # the AOT tier compiles bitcode whose runtime part is instrumented already, so the sanitizer flags
    # go to its link alone (which adds their runtime libraries): ASan's pass would instrument it again
    ccflags = "".join([" " + q(a) for a in flags if not a.startswith("-fsanitize") and not a.startswith("-fno-sanitize")])
    llvm = os.getenv("PYSTACHY_LLVM", "")  # optional directory holding clang, opt, lli, llvm-link, llvm-as
    if llvm != "" and not llvm.endswith("/"):
        llvm = llvm + "/"
    # strip clang's target-cpu/features attributes so LLVM can inline runtime helpers into our code
    strip = "sed -E 's/ \"(target-cpu|target-features|tune-cpu)\"=\"[^\"]*\"//g'"
    # intermediate files go to a private directory (mode 0700, honours TMPDIR), removed on every path below
    tmp = tempfile.mkdtemp()
    ll = tmp + "/prog.ll"
    bc = tmp + "/prog.bc"
    obj = tmp + "/prog.o"
    rll = tmp + "/runtime.ll"
    part = f"{rtb}.{os.getpid()}"  # renamed over the cache only once complete
    rto = rtb[:-3] + ".o"  # the runtime as machine code, for the JIT tier
    f = open(ll, "w", encoding="latin-1")
    f.write(ir)
    f.close()
    msg = ""
    code = sh(f"mkdir -p {q(home + '/build')} && (test {q(rtb)} -nt {q(rtc)} || ({llvm}clang -O2 -S -emit-llvm {q(rtc)} -o {q(rll)}{cflags} -fexceptions && {strip} {q(rll)} | {llvm}llvm-as -o {q(part)} && mv -f {q(part)} {q(rtb)}))")
    if code == 0 and cmd == "run":
        code = sh(f"test {q(rto)} -nt {q(rtc)} || ({llvm}clang -O2 -fPIC -c {q(rtc)} -o {q(part)}{cflags} -fexceptions && mv -f {q(part)} {q(rto)})")
    link = f"{llvm}llvm-link --only-needed {q(ll)} {q(rtb)} -o {q(bc)}"
    if code != 0:
        msg = "cannot build the runtime (are clang and LLVM 18 installed? see PYSTACHY_LLVM, PYSTACHY_CFLAGS)"
    elif cmd == "build":
        # AOT tier: full -O2 over program + runtime as one module (whole-program optimization)
        if out == "":
            out = SRC[:-3] if SRC.endswith(".py") else SRC + ".exe"
        code = sh(f"{link} && {llvm}clang -O2 -c {q(bc)} -o {q(obj)} -Wno-unused-command-line-argument{ccflags} && {llvm}clang {q(obj)} -o {q(out)} -lm{cflags}")
    else:
        # JIT tier: cheap SSA cleanup of the program alone, then LLVM's ORC JIT compiles it for the
        # host CPU and links it with the precompiled runtime (the JIT tier never inlines the runtime)
        fast = f"{llvm}opt -passes='mem2reg,instcombine<no-verify-fixpoint>,simplifycfg'"
        code = sh(f"{fast} {q(ll)} -o {q(bc)}")
        if code == 0:
            # then this process becomes lli, through a shell that opens the bitcode for it and removes
            # the files: the program's end is pystachy run's own, a signal that kills it too
            for p in [ll, obj, rll, part]:
                if os.path.exists(p):
                    os.remove(p)
            run = f"PYSTACHY_ARGV0={q(SRC)} exec {llvm}lli -extra-object={q(rto)} /dev/fd/9 {' '.join([q(a) for a in rest])}"
            os.execv("/bin/sh", ["sh", "-c", f"exec 9< {q(bc)} && rm -f {q(bc)} && rmdir {q(tmp)} && {run}"])
    for p in [ll, bc, obj, rll, part]:
        if os.path.exists(p):
            os.remove(p)
    os.rmdir(tmp)
    if msg != "":
        fail(msg, 0)
    sys.exit(code)


if __name__ == "__main__":
    main()
