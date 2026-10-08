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


def unescape(s: str, line: int) -> str:
    # decode the backslash escapes of a string literal's source text
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c != "\\" or i + 1 >= n:
            out.append(c)
            i += 1
            continue
        e = s[i + 1]
        i += 2
        if e == "\n":
            continue
        if e == "x" or e == "u" or e == "U":
            k = 2 if e == "x" else (4 if e == "u" else 8)
            h = s[i : i + k]
            for d in h:
                if d not in "0123456789abcdefABCDEF":
                    fail(f"truncated \\{e} escape in string literal", line)
            if len(h) != k or int(h, 16) > 1114111:
                fail(f"invalid \\{e} escape in string literal", line)
            out.append(utf8(int(h, 16)))
            i += k
        elif e >= "0" and e <= "7":
            v = ord(e) - 48
            for _ in range(2):
                if i < n and s[i] >= "0" and s[i] <= "7":
                    v = v * 8 + ord(s[i]) - 48
                    i += 1
            out.append(utf8(v))
        elif e == "N":
            fail("\\N{...} escapes are not supported", line)
        elif e in ESCAPES:
            out.append(ESCAPES[e])
        else:
            out.append("\\" + e)
    return "".join(out)


class Tok:
    def __init__(self, kind: str, text: str, line: int):
        self.kind = kind
        self.text = text
        self.line = line


class Lexer:
    def __init__(self, src: str, line: int):
        self.src = src
        self.i = 0
        self.line = line
        self.toks: list[Tok] = []

    def add(self, kind: str, text: str) -> None:
        self.toks.append(Tok(kind, text, self.line))

    def run(self) -> list[Tok]:
        src = self.src
        n = len(src)
        indents = [0]
        depth = 0
        if src.startswith(chr(239) + chr(187) + chr(191)):  # a UTF-8 byte order mark
            self.i = 3
        bol = True
        while self.i < n:
            c = src[self.i]
            if bol and depth == 0:
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
                    fail("tabs are not supported for indentation", self.line)
                bol = False
                if col > indents[-1]:
                    indents.append(col)
                    self.add("indent", "")
                while col < indents[-1]:
                    indents.pop()
                    self.add("dedent", "")
                if col != indents[-1]:
                    fail("inconsistent indentation", self.line)
            elif c == "\n":
                if depth == 0:
                    self.add("nl", "")
                    bol = True
                self.line += 1
                self.i += 1
            elif c == " " or c == "\t" or c == "\r" or c == "\f":
                self.i += 1
            elif c == "#":
                while self.i < n and src[self.i] != "\n":
                    self.i += 1
            elif c == "\\" and src.startswith("\n", self.i + 1):
                self.i += 2
                self.line += 1
            elif c.isdigit() or (c == "." and src[self.i + 1 : self.i + 2].isdigit()):
                self.number()
            elif c.isalpha() or c == "_" or ord(c) >= 128:
                self.word()
            elif c == '"' or c == "'":
                self.string("")
            else:
                self.op()
                k = self.toks[-1].kind
                if k == "(" or k == "[" or k == "{":
                    depth += 1
                elif k == ")" or k == "]" or k == "}":
                    depth -= 1
        if not bol:
            self.add("nl", "")
        while len(indents) > 1:
            indents.pop()
            self.add("dedent", "")
        self.add("eof", "")
        return self.toks

    def number(self) -> None:
        src = self.src
        j = self.i
        pfx = src[j : j + 2].lower()
        if pfx == "0x" or pfx == "0o" or pfx == "0b":
            base = 16 if pfx == "0x" else (8 if pfx == "0o" else 2)
            kind = "hexadecimal" if base == 16 else ("octal" if base == 8 else "binary")
            j += 2
            while j < len(src) and (src[j].isalnum() or src[j] == "_"):
                j += 1
            body = src[self.i + 2 : j]
            for c in body:
                dv = "0123456789abcdef".find(c.lower())
                if c != "_" and (dv < 0 or dv >= base):
                    fail(f"invalid {kind} literal", self.line)
            if body.replace("_", "") == "" or "__" in body or body.endswith("_"):
                fail(f"invalid {kind} literal", self.line)
            h = body.replace("_", "").lstrip("0")
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
        isf = False
        while j < len(src) and (src[j].isdigit() or src[j] == "_"):
            j += 1
        if src.startswith(".", j) and not src.startswith("..", j):
            isf = True
            j += 1
            while j < len(src) and (src[j].isdigit() or src[j] == "_"):
                j += 1
        if j < len(src) and (src[j] == "e" or src[j] == "E"):
            isf = True
            j += 1
            if j < len(src) and (src[j] == "+" or src[j] == "-"):
                j += 1
            if j >= len(src) or not src[j].isdigit():
                fail("invalid float literal", self.line)
            while j < len(src) and (src[j].isdigit() or src[j] == "_"):
                j += 1
        text = src[self.i : j]
        low = text.lower()
        if "__" in text or text.endswith("_") or "_." in text or "._" in text or "_e" in low or "e_" in low:
            fail("invalid decimal literal", self.line)
        if not isf and len(text) > 1 and text[0] == "0" and text.replace("_", "").strip("0") != "":
            fail("leading zeros in decimal integer literals are not permitted", self.line)
        if j < len(src) and (src[j] == "j" or src[j] == "J"):
            self.add("complex", text.replace("_", "") + "j")
            self.i = j + 1
            return
        self.add("float" if isf else "int", text.replace("_", ""))
        self.i = j

    def word(self) -> None:
        src = self.src
        j = self.i
        while j < len(src) and (src[j].isalnum() or src[j] == "_" or ord(src[j]) >= 128):
            j += 1
        w = src[self.i : j]
        for ch in w:
            if ord(ch) >= 128:
                fail("non-ASCII identifiers are not supported", self.line)
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
                fail("unterminated string", line)
            c = src[self.i]
            if c == q and (not triple or src.startswith(q + q + q, self.i)):
                if len(fields) > 0 and fields[-1] >= 0 and not triple and self.reuses_quote(q):
                    fail("f-string: reusing the string's quote inside a replacement field (PEP 701) is not supported; use the other quote", line)
                break
            if "f" in prefix and (len(fields) == 0 or fields[-1] < 0):
                # literal text, or a format spec: {{ and }} are braces, { opens a field, } closes one
                if c == "{" or c == "}":
                    if len(fields) == 0 and src[self.i + 1 : self.i + 2] == c:
                        self.i += 2
                        continue
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
            if c == "\n":
                if not triple:
                    fail("unterminated string", line)
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
        if "f" in prefix:
            # decoded later, piece by piece, so escapes never turn into replacement fields
            self.toks.append(Tok("rfstr" if "r" in prefix else "fstr", text, line))
        elif "b" in prefix:
            self.toks.append(Tok("bytes", text, line))
        else:
            self.toks.append(Tok("str", text if "r" in prefix else unescape(text, line), line))

    def reuses_quote(self, q: str) -> bool:
        # f"{d["k"]}": the quote that would end the f-string inside a field starts a string that
        # closes on this line and is followed by more of the expression; otherwise the field is unclosed
        src = self.src
        j = src.find(q, self.i + 1)
        if j < 0 or src.find("\n", self.i, j) >= 0:
            return False
        k = j + 1
        while k < len(src) and src[k] == " ":
            k += 1
        return k < len(src) and src[k] in "])}.,[!:=+*%<>"

    def op(self) -> None:
        for o in OPS:
            if self.src.startswith(o, self.i):
                self.add(o, o)
                self.i += len(o)
                return
        fail(f"unexpected character {repr(self.src[self.i])}", self.line)


# ---------------------------------------------------------------- parser
class Node:
    def __init__(self, kind: str, s: str, line: int):
        self.kind = kind
        self.s = s
        self.line = line
        self.kids: list[Node] = []
        self.chk = False  # a variable read that may find the variable unassigned


def mk(kind: str, s: str, line: int, kids: list[Node]) -> Node:
    n = Node(kind, s, line)
    n.kids = kids
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


STARTS: dict[str, bool] = {}
for _k in "id int float str fstr rfstr bytes complex ... ( [ { - + ~ not None True False lambda yield".split():
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

    def peek(self) -> str:
        return self.toks[self.p].kind

    def ahead(self) -> str:
        return self.toks[self.p + 1].kind

    def line(self) -> int:
        return self.toks[self.p].line

    def eat(self, k: str) -> bool:
        if self.toks[self.p].kind == k:
            self.p += 1
            return True
        return False

    def expect(self, k: str) -> Tok:
        t = self.toks[self.p]
        if t.kind != k:
            fail(f"expected '{k}' but found '{t.text or t.kind}'", t.line)
        self.p += 1
        return t

    # ---- statements
    def module(self) -> Node:
        body: list[Node] = []
        while self.peek() != "eof":
            if not self.eat("nl"):
                self.stmt(body)
        return mk("block", "", 1, body)

    def scope(self, fn: bool) -> Node:
        # the body of a def (fn) or class: no loop around it
        loops = self.loops
        infn = self.infn
        self.loops = 0
        self.infn = fn
        b = self.block()
        self.loops = loops
        self.infn = infn
        return b

    def block(self) -> Node:
        line = self.line()
        body: list[Node] = []
        if self.eat("nl"):
            self.expect("indent")
            while not self.eat("dedent"):
                if not self.eat("nl"):
                    self.stmt(body)
        else:
            self.simple(body)
        return mk("block", "", line, body)

    def stmt(self, out: list[Node]) -> None:
        k = self.peek()
        line = self.line()
        if k != "from" and k != "import" and not (k == "str" and self.p == 0):
            self.early = False  # from __future__ imports may follow only a docstring
        if k == "def":
            out.append(self.funcdef())
        elif k == "class":
            # class C(bases): a class with bases other than object is a "subclass" node (the class,
            # then the bases), which code generation rejects where it needs the class
            self.p += 1
            name = self.expect("id").text
            bases: list[Node] = []
            tps: list[str] = []
            if self.peek() == "[":
                self.typeparams(tps)
                bases.append(mk("typeparams", "", line, []))  # class C[T]: a generic class
            if self.eat("("):
                while not self.eat(")"):
                    if self.peek() == "id" and self.ahead() == "=":
                        self.p += 2
                        bases.append(mk("kw", self.toks[self.p - 2].text, line, [self.test()]))
                    else:
                        bases.append(self.item())
                    if not self.eat(","):
                        self.expect(")")
                        break
            self.expect(":")
            c = mk("class", name, line, [self.scope(False)])
            if len(bases) == 0 or (len(bases) == 1 and bases[0].kind == "name" and bases[0].s == "object"):
                out.append(c)
            else:
                out.append(mk("subclass", name, line, [c] + bases))
        elif k == "if":
            out.append(self.ifstmt())
        elif k == "while":
            self.p += 1
            c = self.test()
            self.expect(":")
            self.loops += 1
            out.append(mk("while", "", line, [c, self.block()]))
            self.loops -= 1
        elif k == "for":
            self.p += 1
            t = self.targets()
            self.expect("in")
            it = self.exprlist()
            self.expect(":")
            self.loops += 1
            out.append(mk("for", "", line, [t, it, self.block()]))
            self.loops -= 1
        elif k == "@":
            # a decorator: s is its dotted name, a decorator with arguments keeps the call as its kid
            self.p += 1
            e = self.test()
            self.expect("nl")
            self.stmt(out)
            d = out[-1]
            if d.kind == "subclass":
                d = d.kids[0]
            if d.kind != "class" and d.kind != "def":
                fail("invalid syntax: a decorator must precede a def or class", line)
            fn = e.kids[0] if e.kind == "call" else e
            name = ""
            while fn.kind == "attr":
                name = "." + fn.s + name
                fn = fn.kids[0]
            name = (fn.s if fn.kind == "name" else "?") + name
            d.kids.append(mk("deco", name, line, [e] if e.kind == "call" else []))
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
                    it.kids.append(as_target(self.postfix()))
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
            # handler, then the else and finally blocks (blocks with s "else" and "finally")
            self.p += 1
            self.expect(":")
            kids = [self.block()]
            while self.peek() == "except":
                hl = self.line()
                self.p += 1
                self.eat("*")
                typ = mk("omit", "", hl, [])
                name = ""
                if self.peek() != ":":
                    typ = self.test()
                    if self.eat("as"):
                        name = self.expect("id").text
                self.expect(":")
                kids.append(mk("except", name, hl, [typ, self.block()]))
            for w in ["else", "finally"]:
                if self.eat(w):
                    self.expect(":")
                    b = self.block()
                    b.s = w
                    kids.append(b)
            out.append(mk("try", "", line, kids))
        elif k == "async":
            # async def, async with, async for: kept as an "async" node that code generation rejects
            self.p += 1
            inner: list[Node] = []
            self.stmt(inner)
            if inner[0].kind == "def":
                inner[0].kids.append(mk("deco", "async", line, []))
                out.append(inner[0])
            else:
                out.append(mk("async", "", line, inner))
        elif k == "id" and self.toks[self.p].text == "match" and self.soft_match():
            # match subject: case pattern [if guard]: ... -- kept as a "match" node (patterns skipped)
            self.p += 1
            n = mk("match", "", line, [self.exprlist()])
            self.expect(":")
            self.expect("nl")
            self.expect("indent")
            while not self.eat("dedent"):
                if self.eat("nl"):
                    continue
                if self.toks[self.p].text != "case":
                    fail("expected 'case'", self.line())
                depth = 0
                while not (depth == 0 and self.peek() == ":"):
                    if self.peek() == "(" or self.peek() == "[" or self.peek() == "{":
                        depth += 1
                    elif self.peek() == ")" or self.peek() == "]" or self.peek() == "}":
                        depth -= 1
                    elif self.peek() == "eof":
                        fail("expected ':'", self.line())
                    self.p += 1
                self.p += 1
                n.kids.append(self.block())
            out.append(n)
        elif k == "id" and self.toks[self.p].text == "type" and self.ahead() == "id" and (self.toks[self.p + 2].kind == "=" or self.toks[self.p + 2].kind == "["):
            # type X = ... (PEP 695)
            while self.peek() != "nl" and self.peek() != "eof":
                self.p += 1
            self.expect("nl")
            out.append(mk("typealias", "", line, []))
        else:
            self.simple(out)
        if self.peek() == "else" and (k == "for" or k == "while"):
            # for/while ... else: the else block is the loop's last kid, a block with s "else"
            self.p += 1
            self.expect(":")
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
        c = self.test()
        self.expect(":")
        n = mk("if", "", line, [c, self.block(), mk("block", "", line, [])])
        if self.peek() == "elif":
            n.kids[2].kids.append(self.ifstmt())
        elif self.eat("else"):
            self.expect(":")
            n.kids[2] = self.block()
        return n

    def funcdef(self) -> Node:
        line = self.line()
        self.p += 1
        name = self.expect("id").text
        tps: list[str] = []
        if self.peek() == "[":
            self.typeparams(tps)
        self.expect("(")
        # params: s is "<number of positional-only parameters>,<index of the first keyword-only one>"
        # (-1: none); *args and **kwargs are "starparam" and "dstarparam" kids
        params = mk("params", "", line, [])
        seen: dict[str, bool] = {}
        posonly = 0
        kwonly = -1
        slash = False
        star = False  # a * or *args seen
        bare = False  # a bare * not yet followed by a named parameter
        dstar = False
        while not self.eat(")"):
            if dstar:
                fail("arguments cannot follow var-keyword argument", line)
            if self.eat("/"):
                if slash:
                    fail("/ may appear only once", line)
                if kwonly >= 0:
                    fail("/ must be ahead of *", line)
                if len(params.kids) == 0:
                    fail("at least one argument must precede /", line)
                slash = True
                posonly = len(params.kids)
            elif self.peek() == "*" and (self.ahead() == "," or self.ahead() == ")"):
                if star:
                    fail("* argument may appear only once", line)
                self.p += 1
                star = True
                bare = True
                kwonly = len(params.kids)
            else:
                kind = "param"
                if self.eat("*"):
                    kind = "starparam"
                    if star:
                        fail("* argument may appear only once", line)
                    star = True
                elif self.eat("**"):
                    kind = "dstarparam"
                    if bare:
                        fail("named arguments must follow bare *", line)
                    dstar = True
                elif bare:
                    bare = False
                pname = self.expect("id").text
                if pname in seen:
                    fail(f"duplicate argument '{pname}' in function definition", line)
                seen[pname] = True
                ann = mk("noann", "", line, [])
                dflt = mk("noann", "", line, [])
                if self.eat(":"):
                    ann = self.item() if kind == "starparam" and self.peek() == "*" else self.test()
                if kind == "param" and self.eat("="):
                    dflt = self.test()
                elif kind == "param" and kwonly < 0 and len(params.kids) > 0 and params.kids[-1].kids[1].kind != "noann":
                    fail("parameter without a default follows parameter with a default", line)
                params.kids.append(mk(kind, pname, line, [ann, dflt]))
                if kind == "starparam":
                    kwonly = len(params.kids)
            if not self.eat(","):
                self.expect(")")
                break
        if bare:
            fail("named arguments must follow bare *", line)
        params.s = f"{posonly},{kwonly}"
        ret = mk("noann", "", line, [])
        if self.eat("->"):
            ret = self.test()
        self.expect(":")
        # def f[T](x: T) -> T: what mentions a type parameter is left unannotated (a template)
        for p in params.kids:
            if mentions(p.kids[0], tps):
                p.kids[0] = mk("noann", "", line, [])
        if mentions(ret, tps):
            ret = mk("noann", "", line, [])
        return mk("def", name, line, [params, ret, self.scope(True)])

    def typeparams(self, out: list[str]) -> None:
        # [T, U: bound, *Ts, **P, V = default] after a def's or class's name
        self.expect("[")
        while not self.eat("]"):
            if not self.eat("**"):
                self.eat("*")
            out.append(self.expect("id").text)
            if self.eat(":"):
                self.test()
            if self.eat("="):
                self.test()
            if not self.eat(","):
                self.expect("]")
                break

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
            fail("from __future__ imports must occur at the beginning of the file", line)
        if not future and not (k == "str" and self.p == 0):
            self.early = False
        if k == "pass" or k == "break" or k == "continue":
            if k != "pass" and self.loops == 0:
                fail("'break' outside loop" if k == "break" else "'continue' not properly in loop", line)
            self.p += 1
            return mk(k, "", line, [])
        if k == "return":
            if not self.infn:
                fail("'return' outside function", line)
            self.p += 1
            if self.peek() == "nl" or self.peek() == ";":
                return mk("return", "", line, [])
            return mk("return", "", line, [self.exprlist()])
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
            flat_del(self.test(), n.kids)
            while self.eat(","):
                if self.peek() == "nl" or self.peek() == ";":
                    break
                flat_del(self.test(), n.kids)
            return n
        if k == "nonlocal":
            self.p += 1
            n = mk("nonlocal", "", line, [])
            while True:
                n.kids.append(mk("name", self.expect("id").text, line, []))
                if not self.eat(","):
                    return n
        e = self.exprlist()
        if e.kind == "name" and e.s == "print" and (self.peek() in STARTS or self.peek() == "id"):
            fail("Missing parentheses in call to 'print'. Did you mean print(...)?", line)
        if self.eat(":"):
            n = mk("annassign", "", line, [e, self.test()])
            if self.eat("="):
                n.kids.append(self.exprlist())
            return n
        if self.peek() == "=":
            n = mk("assign", "", line, [as_target(e)])
            while self.eat("="):
                n.kids.append(self.exprlist())
            for i in range(1, len(n.kids) - 1):
                as_target(n.kids[i])
            return n
        k = self.peek()
        if k in AUGOPS:
            self.p += 1
            return mk("augassign", k[:-1], line, [e, self.exprlist()])
        return mk("expr", "", line, [e])

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
            if x == "*" or not self.eat(",") or (paren and self.peek() == ")"):
                break
        if paren:
            self.expect(")")
        return n

    # ---- expressions
    def exprlist(self) -> Node:
        line = self.line()
        e = self.item()
        if self.peek() != ",":
            return e
        t = mk("tuple", "", line, [e])
        while self.eat(","):
            if self.peek() not in STARTS and self.peek() != "*":
                break
            t.kids.append(self.item())
        return t

    def item(self) -> Node:
        if self.peek() == "*":
            line = self.line()
            self.p += 1
            return mk("starred", "", line, [self.binary(0)])
        return self.test()

    def targets(self) -> Node:
        line = self.line()
        e = self.item() if self.peek() == "*" else self.postfix()
        if self.peek() != ",":
            return as_target(e)
        t = mk("tuple", "", line, [e])
        while self.eat(","):
            if self.peek() == "in":
                break
            t.kids.append(self.item() if self.peek() == "*" else self.postfix())
        return as_target(t)

    def test(self) -> Node:
        line = self.line()
        if self.eat("lambda"):
            # lambda params: body (kids: the parameter names, then the body)
            n = mk("lambda", "", line, [])
            while not self.eat(":"):
                if self.eat("*") or self.eat("**") or self.eat("/") or self.eat(","):
                    continue
                n.kids.append(mk("name", self.expect("id").text, line, []))
                if self.eat("="):
                    self.test()
            n.kids.append(self.test())
            return n
        e = self.or_test()
        if self.peek() == ":=" and e.kind == "name":
            self.p += 1
            return mk("walrus", e.s, line, [self.test()])
        if self.eat("if"):
            c = self.or_test()
            self.expect("else")
            return mk("ifexp", "", line, [c, e, self.test()])
        return e

    def or_test(self) -> Node:
        e = self.and_test()
        while self.peek() == "or":
            line = self.line()
            self.p += 1
            e = mk("boolop", "or", line, [e, self.and_test()])
        return e

    def and_test(self) -> Node:
        e = self.not_test()
        while self.peek() == "and":
            line = self.line()
            self.p += 1
            e = mk("boolop", "and", line, [e, self.not_test()])
        return e

    def not_test(self) -> Node:
        line = self.line()
        if self.eat("not"):
            return mk("unary", "not", line, [self.not_test()])
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
            kids.append(self.binary(0))
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
            return mk("unary", k, line, [self.unary()])
        e = self.postfix()
        if self.peek() == "**":
            line = self.line()
            self.p += 1
            return mk("binop", "**", line, [e, self.unary()])
        return e

    def postfix(self) -> Node:
        e = self.atom()
        while True:
            line = self.line()
            if self.eat("("):
                c = mk("call", "", line, [e])
                kws: dict[str, bool] = {}
                gen = False
                while not self.eat(")"):
                    if self.peek() == "*" or self.peek() == "**":
                        star = "starred" if self.peek() == "*" else "dstar"
                        self.p += 1
                        c.kids.append(mk(star, "", line, [self.test()]))
                        if not self.eat(","):
                            self.expect(")")
                            break
                        continue
                    if self.peek() == "id" and self.ahead() == "=":
                        name = self.toks[self.p].text
                        if name in kws:
                            fail(f"keyword argument repeated: {name}", line)
                        kws[name] = True
                        self.p += 2
                        c.kids.append(mk("kw", name, line, [self.test()]))
                    else:
                        if len(kws) > 0:
                            fail("positional argument follows keyword argument", line)
                        a = self.test()
                        if self.compnext():
                            a = self.comp(a, line)
                            a.s = "gen"
                            gen = True
                        c.kids.append(a)
                    if not self.eat(","):
                        self.expect(")")
                        break
                    if gen:
                        fail("Generator expression must be parenthesized", line)
                if gen and len(c.kids) > 2:
                    fail("Generator expression must be parenthesized", line)
                e = c
            elif self.eat("["):
                # x[i], x[lo:hi], x[lo:hi:step] (a step is a fourth kid, which code generation
                # rejects); x[a, b] indexes with a tuple
                items: list[Node] = [self.subscript(line)]
                comma = False
                while self.eat(","):
                    comma = True
                    if self.peek() == "]":
                        break
                    items.append(self.subscript(line))
                self.expect("]")
                if not comma and items[0].kind == "sliceitem":
                    e = mk("slice", "", line, [e] + items[0].kids)
                else:
                    e = mk("index", "", line, [e, items[0] if not comma else mk("tuple", "", line, items)])
            elif self.eat("."):
                e = mk("attr", self.expect("id").text, line, [e])
            else:
                return e

    def subscript(self, line: int) -> Node:
        # one item of a subscript: an expression, *x, or lo:hi[:step] (a "sliceitem")
        if self.peek() == "*":
            return self.item()
        lo = mk("omit", "", line, [])
        if self.peek() != ":":
            lo = self.test()
        if not self.eat(":"):
            return lo
        n = mk("sliceitem", "", line, [lo, mk("omit", "", line, [])])
        if self.peek() != "]" and self.peek() != ":" and self.peek() != ",":
            n.kids[1] = self.test()
        if self.eat(":") and self.peek() != "]" and self.peek() != ",":
            n.kids.append(self.test())
        return n

    def comp(self, e: Node, line: int) -> Node:
        # [e for t in it if c]; with more for and if clauses a "nestedcomp" node, with async for
        # an "asynccomp" one
        aio = self.eat("async")
        self.expect("for")
        t = self.targets()
        self.expect("in")
        n = mk("listcomp", "", line, [e, t, self.or_test()])
        if self.eat("if"):
            n.kids.append(self.or_test())
        while self.compnext() or self.peek() == "if":
            n.kind = "nestedcomp"
            if self.eat("if"):
                n.kids.append(self.or_test())
            else:
                aio = self.eat("async") or aio
                self.p += 1
                n.kids.append(self.targets())
                self.expect("in")
                n.kids.append(self.or_test())
        if aio:
            n.kind = "asynccomp"
        return n

    def atom(self) -> Node:
        t = self.toks[self.p]
        self.p += 1
        k = t.kind
        line = t.line
        if k == "id":
            return mk("name", t.text, line, [])
        if k == "int" or k == "float" or k == "complex":
            return mk(k, t.text, line, [])
        if k == "bytes" or k == "...":
            while k == "bytes" and self.peek() == "bytes":
                self.p += 1
            return mk("bytes" if k == "bytes" else "ellipsis", "", line, [])
        if k == "await":
            return mk("await", "", line, [self.unary()])
        if k == "yield":
            n = mk("yield", "", line, [])
            if self.eat("from"):
                n.kids.append(self.test())
            elif self.peek() in STARTS or self.peek() == "*":
                n.kids.append(self.exprlist())
            return n
        if k == "str" or k == "fstr" or k == "rfstr":
            # adjacent literals concatenate; any f-string among them makes the whole an f-string
            parts: list[Tok] = [t]
            while self.peek() == "str" or self.peek() == "fstr" or self.peek() == "rfstr":
                parts.append(self.toks[self.p])
                self.p += 1
            n = mk("fstr", "", line, [])
            for pt in parts:
                if pt.kind == "str":
                    n.kids.append(mk("str", pt.text, pt.line, []))
                else:
                    self.fparts(pt.text, pt.kind == "rfstr", pt.line, n)
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
            e = self.item() if self.peek() != "yield" else self.atom()
            if self.compnext():
                e = self.comp(e, line)
                e.s = "gen"
            elif self.peek() == ",":
                e = mk("tuple", "", line, [e])
                while self.eat(","):
                    if self.peek() == ")":
                        break
                    e.kids.append(self.item())
            self.expect(")")
            return e
        if k == "[":
            items: list[Node] = []
            if self.peek() != "]":
                e = self.item()
                if self.compnext():
                    e = self.comp(e, line)
                    self.expect("]")
                    return e
                items.append(e)
                while self.eat(","):
                    if self.peek() == "]":
                        break
                    items.append(self.item())
            self.expect("]")
            return mk("list", "", line, items)
        if k == "{":
            # a dict display; set displays and comprehensions, and dict comprehensions, are their own nodes
            d = mk("dict", "", line, [])
            while not self.eat("}"):
                if self.eat("**"):
                    d.kind = "dstar"
                    d.kids.append(self.binary(0))
                else:
                    d.kids.append(self.item())
                    if self.peek() != ":":
                        d.kind = "set"
                    else:
                        self.p += 1
                        d.kids.append(self.test())
                if self.compnext():
                    c = self.comp(d.kids[-1], line)
                    d = mk("dictcomp" if d.kind == "dict" else "setcomp", "", line, [c])
                    self.expect("}")
                    break
                if not self.eat(","):
                    self.expect("}")
                    break
            return d
        fail(f"unexpected '{t.text or k}'", line)
        return mk("omit", "", line, [])

    def fparts(self, s: str, raw: bool, line: int, n: Node) -> None:
        # the parts of an f-string body (or of a format spec with nested fields), appended to n:
        # literal text as str nodes, each replacement field as fmt(expression, spec)
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
                # the expression ends at a top-level '}', ':' or '!' (but not '!=')
                j = i + 1
                depth = 0
                while j < len(s) and (depth > 0 or not (s[j] == "}" or s[j] == ":" or (s[j] == "!" and s[j + 1 : j + 2] != "="))):
                    if s[j] == "'" or s[j] == '"':
                        q = s[j]
                        j += 1
                        while j < len(s) and s[j] != q:
                            j += 2 if s[j] == "\\" else 1
                        if j >= len(s):
                            fail("f-string: unterminated string", line)
                    elif s[j] == "(" or s[j] == "[" or s[j] == "{":
                        depth += 1
                    elif s[j] == ")" or s[j] == "]" or s[j] == "}":
                        depth -= 1
                    j += 1
                if j >= len(s):
                    fail("f-string: expecting '}'", line)
                self.flush(lit, raw, line, n)
                lit = []
                text = s[i + 1 : j]
                src = text.rstrip()
                selfdoc = src.endswith("=") and not (src.endswith("==") or src.endswith("!=") or src.endswith("<=") or src.endswith(">="))
                if selfdoc:
                    # f"{x=}" prints the expression's text, then its value
                    n.kids.append(mk("str", text, line, []))
                    src = src[:-1]
                if src.strip() == "":
                    fail("f-string: valid expression required before '}'", line)
                # (in parentheses, an expression may continue over lines: f"""{x\n + 1}""")
                sub = Parser(Lexer("(" + src.strip() + "\n)", line).run())
                sub.expect("(")
                e = sub.test()
                if sub.peek() != ")":
                    fail("f-string: invalid syntax", line)
                conv = ""
                if s[j] == "!":
                    conv = s[j + 1 : j + 2]
                    if conv != "r" and conv != "s" and conv != "a":
                        fail(f"f-string: invalid conversion character '{conv}': expected 's', 'r', or 'a'", line)
                    j += 2
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
                        spec = mk("str", st if raw else unescape(st, line), line, [])
                    j = k
                if j >= len(s) or s[j] != "}":
                    fail("f-string: expecting '}'", line)
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

    def flush(self, lit: list[str], raw: bool, line: int, n: Node) -> None:
        if len(lit) > 0:
            n.kids.append(mk("str", "".join(lit) if raw else unescape("".join(lit), line), line, []))


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
        self.fails = ""  # the exception its top-level code surely raises, ImportError or ModuleNotFoundError
        # a package's names that an import of the submodule of that name rebinds at a time Pystachy
        # cannot tell (Loader.submodules()); True if that may happen while its own code runs
        self.amb: dict[str, bool] = {}


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


# modules built into CPython 3.13 (as Debian and Ubuntu build it, sys.builtin_module_names): a
# file of that name on the path never replaces them, so Pystachy treats them as missing
CBUILTIN: dict[str, bool] = {}
for _k in ("_abc _ast _bisect _blake2 _codecs _collections _csv _datetime _elementtree _functools _heapq _imp _io _locale "
           "_md5 _opcode _operator _pickle _posixsubprocess _random _sha1 _sha2 _sha3 _signal _socket _sre _stat "
           "_statistics _string _struct _suggestions _symtable _sysconfig _thread _tokenize _tracemalloc _typing _warnings "
           "_weakref array atexit binascii cmath faulthandler fcntl gc grp itertools marshal posix pwd pyexpat select "
           "syslog unicodedata zlib").split():
    CBUILTIN[_k] = True


def builtin_module(path: str) -> bool:
    root = path[: path.find(".")] if "." in path else path
    return path in MODULES or root in MODULES


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


def is_main_guard(st: Node) -> bool:
    # if __name__ == "__main__":
    if st.kind != "if" or st.kids[0].kind != "cmp" or st.kids[0].s != "==":
        return False
    a = st.kids[0].kids[0]
    b = st.kids[0].kids[1]
    if a.kind == "str":
        c = a
        a = b
        b = c
    return a.kind == "name" and a.s == "__name__" and b.kind == "str" and b.s == "__main__"


def import_error(e: Node) -> str:
    # "ImportError" or "ModuleNotFoundError" if raise e raises it, else ""
    n = e.kids[0] if e.kind == "call" else e
    return n.s if n.kind == "name" and (n.s == "ImportError" or n.s == "ModuleNotFoundError") else ""


def bare_raise(n: Node) -> bool:
    # does n hold a raise that re-raises (outside the functions and classes it defines)
    if n.kind == "raise" and len(n.kids) == 0:
        return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass":
        return False
    for k in n.kids:
        if bare_raise(k):
            return True
    return False


def special_import(st: Node, a: Node) -> bool:
    # an import the loader recognizes where the name it binds is read: of a builtin module (import
    # os, import os.path as p), or from typing import TYPE_CHECKING
    if st.s == "":
        return builtin_module(a.kids[1].s)
    return st.s == "from" and (a.kids[0].s == "typing.TYPE_CHECKING" or a.kids[0].s == "typing_extensions.TYPE_CHECKING")


def binds(body: list[Node], out: dict[str, bool], special: bool) -> None:
    # the names statements bind in their own scope (not inside the functions and classes they
    # define): assignments, del, def and class, except ... as, and imports (only with special those
    # special_import() recognizes)
    for st in body:
        targets(st, out)
        if st.kind == "import":
            for a in st.kids:
                if a.s != "*" and (special or not special_import(st, a)):
                    out[a.s] = True
        elif st.kind == "del":
            for t in st.kids:
                if t.kind == "name":
                    out[t.s] = True
        elif st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            out[st.s] = True
            continue
        for kid in st.kids:
            if kid.kind == "block":
                binds(kid.kids, out, special)
            elif kid.kind == "except":
                if kid.s != "":
                    out[kid.s] = True
                binds(kid.kids[1].kids, out, special)


def rebound(body: list[Node]) -> dict[str, bool]:
    # the names a module binds other than by the imports special_import() recognizes, also through a
    # function's global statement: such a name is never taken for os, sys or TYPE_CHECKING
    out: dict[str, bool] = {}
    binds(body, out, False)
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
    for nm in decl:
        if nm in out:
            del out[nm]
    return out


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
        self.curdef = ""  # the def whose body imports() is in
        self.fk: dict[str, str] = {}  # the bindings of the function being qualified
        self.parsed: dict[str, Node] = {}  # each module file, parsed once
        # each optional import that optional() decided: s is the module whose import fails, if its
        # code raises ImportError, and the kids are the other modules whose code runs in the try;
        # with the module it is in, and whether other statements run in the try too (checked by guarded())
        self.sites: list[Node] = []
        self.sitem: list[Mod] = []
        self.siteall: list[bool] = []
        # each from-import of a name a package binds itself (take()), with the bindings it went to,
        # for submodules(): s is the name bound, the kids the package, the name and the copy if any
        self.taken: list[Node] = []
        self.takek: list[dict[str, str]] = []
        self.qdef = False  # is qstmts() in a function

    def program(self, path: str, src: str) -> list[Mod]:
        # the main program and the modules it imports, in the order their code may first run
        m = Mod("", path, "")
        FILES.append(path)
        m.body = Parser(Lexer(src, 1).run()).module()
        m.rebound = rebound(m.body.kids)
        self.simplify(m, m.body, {})
        self.bindings(m)
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
                    self.bind(self.laterm[i], a.s, "x:" + msg, True)
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
            fail(f"module '{name}' is not supported: it is not a builtin module ({', '.join(MODULES.keys())}) and there is no {name[dot + 1 :]}.py on the module path", line)
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
        m.rebound = rebound(m.body.kids)
        r: list[Node] = []
        if self.init_raise(m, m.body.kids, r) and len(r) > 0:
            r[0].s = "init"  # (an optional import of the module returns there instead: Gen.raise_stmt)
            m.fails = import_error(r[0].kids[0])
        self.simplify(m, m.body, {})
        self.bindings(m)
        self.imports(m, m.body, False)
        self.order.append(m)
        return m

    def parse(self, path: str) -> Node:
        # a module's file, parsed once (optional() may look at it before it is loaded)
        if path in self.parsed:
            return self.parsed[path]
        f = open(path, "r", encoding="latin-1")
        src = f.read()
        f.close()
        k = len(FILES)
        FILES.append(path[2:] if path.startswith("./") else path)
        self.parsed[path] = Parser(Lexer(src, k * LINES + 1).run()).module()
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
                    if nm == "__debug__":
                        fail("cannot assign to __debug__", st.line)
                    m.kinds[nm] = "v"
                    if nm in m.fnonly:
                        del m.fnonly[nm]
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

    def simplify(self, m: Mod, blk: Node, scope: dict[str, bool]) -> None:
        # what the loader decides about blk before anything else (scope: the names that the function
        # or class blk is in binds itself, which hide the module's): the if statements and optional
        # imports CPython decides at import time (static_if(), optional()) leave what runs in their
        # place; a module-level alias of a def or class (bisect = bisect_right) binds the same
        # function or class, and is no statement at run time
        out: list[Node] = []
        for st in blk.kids:
            if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "attr" and st.kids[0].s == "__doc__" and st.kids[0].kids[0].kind == "name" and blk is m.body:
                # f.__doc__ = g.__doc__: docstrings cannot be read in Pystachy, so this is dropped
                continue
            run: list[Node] = []
            if self.static_if(m, st, scope, run) or self.optional(m, st, run):
                b = mk("block", "", st.line, run)
                self.simplify(m, b, scope)
                out.extend(b.kids)
            else:
                out.append(st)
                inner = scope_names(st) if st.kind == "def" or st.kind == "class" else scope
                decl: dict[str, bool] = {}
                if st.kind == "def":
                    globals_in(st.kids[2].kids, decl)
                for kid in st.kids:
                    if kid.kind == "block":
                        self.simplify(m, kid, inner)
                if st.kind == "def":
                    self.dropped_locals(st, inner, decl)
        blk.kids = out

    def dropped_locals(self, d: Node, before: dict[str, bool], decl: dict[str, bool]) -> None:
        # what function d binds only in code simplify() dropped still decides its scope in CPython: a
        # global statement there holds for the whole function (it is kept), and a name bound there is
        # a local, which a read then finds unbound (an error where d is compiled)
        now: dict[str, bool] = {}
        globals_in(d.kids[2].kids, now)
        for nm in decl:
            if nm not in now:
                d.kids[2].kids.insert(0, mk("global", "", d.line, [mk("name", nm, d.line, [])]))
        now = scope_names(d)
        for nm in before:
            if nm not in now and refers(d.kids[2], nm):
                msg = f"'{nm}' is local to {d.s}() only through code that is dropped at compile time (for the platform, TYPE_CHECKING or an import that fails), so reading it is not supported"
                d.kids[2].kids.insert(0, mk("badimport", msg, d.line, []))

    def static_if(self, m: Mod, st: Node, scope: dict[str, bool], out: list[Node]) -> bool:
        # an if statement CPython decides at import time, as Pystachy does at compile time: a test of
        # the platform or of TYPE_CHECKING (decide()), or in an imported module if __name__ ==
        # "__main__": (false). Appends what runs to out; False if st is none of these
        if st.kind != "if":
            return False
        pre: list[Node] = []
        r = self.decide(m, st.kids[0], scope, pre)
        if r < 0 and m.name != "" and is_main_guard(st) and "__name__" not in scope and "__name__" not in m.rebound:
            r = 0
        if r < 0:
            return False
        out.extend(pre)
        out.extend(st.kids[1].kids if r == 1 else st.kids[2].kids)
        return True

    def optional(self, m: Mod, st: Node, out: list[Node]) -> bool:
        # try: <imports, then other statements> / except ImportError: <handler> (an optional module,
        # accel_try()), decided at compile time: the imports run in order until one fails, because
        # its module is not found (the code of its packages runs first) or because the module's code
        # raises ImportError at its top level (init_raise(): its code before the raise runs, guarded
        # so that it returns there). Then the handler that catches the exception runs; if none
        # fails, the rest of the body and the else block do. Appends what runs to out; False if st is
        # not such a try
        if not accel_try(st):
            return False
        line = st.line
        site = mk("pass", "", line, [])  # (for guarded(), which may make it an error)
        out.append(site)
        run: list[Node] = []  # the imports that succeed, then the one that fails
        bad = ""  # the module whose import fails
        exc = "ModuleNotFoundError"
        for x in st.kids[0].kids:
            if x.kind != "import" or bad != "":
                break
            ok: list[Node] = []
            for a in x.kids:
                p = a.kids[1].s if not x.s.startswith("from.") else self.relative(m, x.s, a.kids[1].s, x.line)
                i = 0
                while i >= 0 and bad == "" and not builtin_module(p):
                    # each package on the way, then the module
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
                if x.s.startswith("from") and a.s != "*":
                    site.kids.append(mk("str", p + "." + a.kids[0].s[a.kids[0].s.rfind(".") + 1 :], line, []))  # (if a submodule)
            if len(ok) == len(x.kids):
                run.append(x)
            elif len(ok) > 0:
                run.append(mk("import", x.s, x.line, ok))
        h = 0  # the handler that catches the exception
        for j in range(1, len(st.kids)):
            if st.kids[j].kind == "except" and h == 0:
                t = st.kids[j].kids[0]
                for e in t.kids if t.kind == "tuple" else [t]:
                    if e.s == "ImportError" or e.s == exc:
                        h = j
        missing = bad != "" and exc == "ModuleNotFoundError" and self.modpath(bad) == ""
        if bad != "" and not missing:
            site.s = bad
        self.sites.append(site)
        self.sitem.append(m)
        self.siteall.append(bad == "" and len(run) < len(st.kids[0].kids))
        if bad == "" or h == 0:
            # every import succeeds, or the exception is not caught: the body runs (the failing
            # module's raise ends the program, as in CPython), then the else block
            out.extend(st.kids[0].kids)
            for e in st.kids[1:]:
                if e.kind == "block" and e.s == "else":
                    out.extend(e.kids)
            return True
        b = st.kids[h].kids[1]
        if st.kids[h].s != "" or bare_raise(b) or (missing and len(b.kids) == 1 and b.kids[0].kind == "raise"):
            # the handler needs the exception, or raises: the module is required
            if missing:
                msg = f"module '{bad}' is not supported: it is not a builtin module and there is no {bad[bad.rfind('.') + 1 :]}.py on the module path"
            else:
                msg = f"module '{bad}' raises {exc} as it initializes, and an except clause that re-raises or names the exception is not supported"
            out.append(mk("badimport", msg, line, []))
            return True
        out.extend(run)
        par = bad[: bad.rfind(".")] if missing and "." in bad else "" if missing else bad
        if par != "":
            # the code of the failing module's packages runs (and its own until its raise), binding nothing
            al = mk("alias", "", line, [mk("str", par, line, []), mk("str", par, line, [])])
            if not missing:
                al.kids.append(mk("guard", "", line, []))
            out.append(mk("import", "", line, [al]))
        out.extend(b.kids)
        return True

    def init_fails(self, name: str) -> str:
        # the exception module name's code raises at its top level for sure (init_raise()), or ""
        if name in self.mods:
            return self.mods[name].fails
        p = self.modpath(name)
        if not p.endswith(".py"):
            return ""  # (a namespace package has no code)
        t = Mod(name, p, "")
        t.body = self.parse(p)
        t.rebound = rebound(t.body.kids)
        r: list[Node] = []
        self.init_raise(t, t.body.kids, r)
        return import_error(r[0].kids[0]) if len(r) > 0 else ""

    def init_raise(self, m: Mod, body: list[Node], out: list[Node]) -> bool:
        # the raise of ImportError (or ModuleNotFoundError) that module m's code reaches for sure at its
        # top level, where simplify() leaves it, goes to out; True once it is found, or once an
        # optional import (which simplify() decides) leaves it unsure
        for st in body:
            run: list[Node] = []
            if st.kind == "raise" and len(st.kids) > 0 and import_error(st.kids[0]) != "":
                out.append(st)
                return True
            if accel_try(st) or (self.static_if(m, st, {}, run) and self.init_raise(m, run, out)):
                return True
        return False

    def guarded(self) -> None:
        # an optional import is decided at compile time, so the code that runs in its try must not
        # raise ImportError in another way: neither the code of the modules it imports (and of the
        # modules they import) nor, if other statements run in the try, that of its own module. The
        # site (a pass statement where the try was) becomes an error where it is compiled.
        for i in range(len(self.sites)):
            s = self.sites[i]
            seen: dict[str, bool] = {}
            why = ""
            for x in s.kids:
                if x.s in self.mods and why == "" and self.raises(self.mods[x.s], "", seen):
                    why = f"the code of module '{x.s}'"
            if s.s in self.mods and why == "" and self.raises(self.mods[s.s], s.s, {}):
                why = f"the code of module '{s.s}', besides its top-level raise,"
            if self.siteall[i] and why == "" and self.raises(self.sitem[i], "", seen):
                why = "the code that runs in the try"
            msg = f"{why} may raise ImportError, which the except clause would catch: not supported (Pystachy decides optional imports at compile time)"
            if s.s in self.mods and why == "" and self.imports_mod(self.mods[s.s].body, self.sitem[i].name, {}):
                # (where its code runs this import, CPython's finds the module half run, and succeeds)
                msg = f"module '{s.s}' imports this module as its code runs, before that raises ImportError: an optional import of it here is not supported"
                why = s.s
            s.kids = []
            if why != "":
                s.kind = "badimport"
                s.s = msg

    def raises(self, m: Mod, ok: str, seen: dict[str, bool]) -> bool:
        # may module m's code, or the code of a module it imports, raise ImportError (other than the
        # top-level raise of module ok, which an optional import guards)?
        if m.name in seen:
            return False
        seen[m.name] = True
        return self.raises_in(m.body, m.name == ok, seen)

    def raises_in(self, n: Node, ok: bool, seen: dict[str, bool]) -> bool:
        if n.kind == "raise" and len(n.kids) > 0 and import_error(n.kids[0]) != "" and not (ok and n.s == "init"):
            return True
        if n.kind == "uimport":
            for x in n.kids:
                if x.kind == "str" and x.s in self.mods and self.raises(self.mods[x.s], "", seen):
                    return True
        for k in n.kids:
            if self.raises_in(k, ok, seen):
                return True
        return False

    def imports_mod(self, n: Node, name: str, seen: dict[str, bool]) -> bool:
        # does code n import module name, itself or through the modules it imports?
        if n.kind == "uimport":
            for x in n.kids:
                if x.s == name:
                    return True
                if x.s in self.mods and x.s not in seen:
                    seen[x.s] = True
                    if self.imports_mod(self.mods[x.s].body, name, seen):
                        return True
        for k in n.kids:
            if self.imports_mod(k, name, seen):
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
                    t.amb[x] = self.imports_mod(t.body, sub, {})
        for i in range(len(self.taken)):
            n = self.taken[i]
            t = self.mods[n.kids[0].s]
            x = n.kids[1].s
            if x in t.amb:
                # (import t.x as y runs the submodule's code after t's, so t's x is the submodule from
                # then on, unless the submodule's code may run within t's or a function of t rebinds x)
                sure = n.kind == "takesub" and not t.amb[x] and x not in t.fnglobal
                msg = self.ambiguous(t.name, x)
                if len(n.kids) > 2:
                    n.kids[2].kind = "pass" if sure else "badimport"  # (the copy of a variable)
                    n.kids[2].s = msg
                    n.kids[2].kids = []
                self.takek[i][n.s] = "m:" + t.name + "." + x if sure else "x:" + msg

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
        # "nt"), or TYPE_CHECKING (false), also under not/and/or: 1 or 0, after appending to pre what
        # still runs for the other operands, in CPython's order ("if x: pass" for an operand x that
        # is evaluated and tested); -1 if e is undecided
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
        other = "win32 cygwin msys nt java emscripten wasi ios android"
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
        # is in) does not hide it, if m binds it only by imports special_import() recognizes at its
        # top level: a builtin module (import sys, import os as _os: "sys", "os") or
        # "typing.TYPE_CHECKING"; else ""
        if name in scope or name in m.rebound:
            return ""
        r = ""
        for st in m.body.kids:
            for a in st.kids if st.kind == "import" else st.kids[:0]:
                if a.s == name:
                    t = a.kids[0].s if st.s == "" else "typing.TYPE_CHECKING"
                    if not special_import(st, a) or (r != "" and r != t):
                        return ""
                    r = t
        return r

    def imports(self, m: Mod, blk: Node, infn: bool) -> None:
        # load the user modules that the import statements in blk name, and rewrite those
        out: list[Node] = []
        for st in blk.kids:
            if st.kind == "import" and infn:
                for a in st.kids:
                    if a.s == "*":
                        fail("import * only allowed at module level", st.line)
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
                for kid in st.kids:
                    if kid.kind == "block":
                        self.imports(m, kid, infn or st.kind == "def")
                self.curdef = saved
        blk.kids = out

    def bind(self, m: Mod, name: str, k: str, infn: bool) -> None:
        # what an import binds name to; in a function, for that function only
        if infn:
            self.fks[self.curdef][name] = k
        else:
            m.kinds[name] = k

    def import_stmt(self, m: Mod, st: Node, infn: bool, out: list[Node]) -> None:
        # one import statement becomes: an import node with its builtin modules (for code
        # generation), a uimport node with the user modules to initialize (each package before
        # its submodules), and for every variable taken with from-import an assignment of its
        # current value, as CPython binds it
        line = st.line
        keep = mk("import", st.s, line, [])
        inits = mk("uimport", "", line, [])
        copies: list[Node] = []
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
                if a.s == "*":
                    fail(f"'from {path} import *' is not supported", line)
                self.bind(m, a.s, "b:" + a.kids[0].s, infn)
                keep.kids.append(a)
                continue
            if infn and not builtin_module(path) and self.modpath(path) == "":
                # a module that cannot be found, imported by a function: an error only where the
                # function is compiled, as CPython's ImportError comes only where it runs
                msg = f"module '{path}' is not supported: it is not a builtin module and there is no {path[path.rfind('.') + 1 :]}.py on the module path"
                out.append(mk("badimport", msg, line, []))
                self.bind(m, a.s, "x:" + msg, infn)
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
                # submodule, unless a.b binds c itself
                tgt = a.kids[0].s
                n = len(self.taken)
                self.take(m, self.mods[tgt[: tgt.rfind(".")]], tgt[tgt.rfind(".") + 1 :], a.s, infn, keep, inits, copies, line)
                if len(self.taken) > n:
                    self.taken[n].kind = "takesub"  # (this import runs the submodule's code: submodules())
            elif st.s == "":
                # import a.b.c binds a; import a as x binds x to a
                self.bind(m, a.s, "m:" + a.kids[0].s, infn)
            elif a.s == "*":
                for x in self.public(src):
                    self.take(m, src, x, x, infn, keep, inits, copies, line)
            else:
                tgt = a.kids[0].s
                self.take(m, src, tgt[tgt.rfind(".") + 1 :], a.s, infn, keep, inits, copies, line)
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
        if not infn and (m.kinds.get(name, "") == "f" or m.kinds.get(name, "") == "c"):
            fail(f"'{name}' is bound both by an import and by a def or class (not supported)", line)
        if not infn and m.kinds.get(name, "") == "v" and k != "v" and k != "":
            fail(f"'{name}' is bound both as a variable and by an import (not supported)", line)
        if k == "" and src.pdir != "":
            # a submodule of the package
            sub = src.name + "." + x
            self.find(sub, line)
            inits.kids.append(mk("str", sub, line, []))
            self.bind(m, name, "m:" + sub, infn)
        elif k == "":
            fail(f"cannot import name '{x}' from '{src.name}'", line)
        elif k == "f" or k == "c":
            self.bind(m, name, "a:" + src.q + x, infn)
        elif k.startswith("b:"):
            p = k[2:]
            self.bind(m, name, k, infn)
            keep.kids.append(mk("alias", name, line, [mk("str", p, line, []), mk("str", p[: p.find(".")] if "." in p else p, line, [])]))
        elif k != "v":
            self.bind(m, name, k, infn)
        else:
            if not infn:
                m.kinds[name] = "v"
            copies.append(mk("assign", "", line, [mk("name", name, line, []), mk("name", src.q + x, line, [])]))
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
            n.s = f"module '{base}' has no attribute '{n.s}'"
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
                n.kind = "str"
                n.s = m.name
                return
            mod = self.qmod(m, n, loc)
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
            self.qexpr(m, n.kids[2], loc)
            inner = dict(loc)
            names: list[str] = []
            names_in(n.kids[1], names)
            for nm in names:
                inner[nm] = True
            for i in range(len(n.kids)):
                if i != 2:
                    self.qexpr(m, n.kids[i], inner)
        else:
            for kid in n.kids:
                self.qexpr(m, kid, loc)

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

    def qstmts(self, m: Mod, body: list[Node], loc: dict[str, bool], cls: bool) -> None:
        for st in body:
            k = st.kind
            if k == "def":
                if not cls:
                    st.s = self.qname(m, st.s, loc)
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
                for p in st.kids[0].kids:
                    if p.s in decl:
                        fail(f"name '{p.s}' is parameter and global", st.line)
                global_order(st.kids[2].kids, {}, decl)
                for nm in decl:
                    if nm in inner:
                        del inner[nm]
                saved = self.fk
                indef = self.qdef
                self.fk = self.fks.get(str(st.line), {})
                self.qdef = True
                self.qstmts(m, st.kids[2].kids, inner, False)
                self.qdef = indef
                self.fk = saved
            elif k == "subclass":
                self.qstmts(m, [st.kids[0]], loc, cls)
                st.s = st.kids[0].s
                for kid in st.kids[1:]:
                    self.qexpr(m, kid, loc)
            elif k == "class":
                st.s = self.qname(m, st.s, loc)
                for d in st.kids[1:]:
                    root = d.s[: d.s.find(".")] if "." in d.s else d.s
                    d.s = self.qname(m, root, loc) + d.s[len(root) :]
                self.qstmts(m, st.kids[0].kids, loc, True)
            elif cls and k == "assign":
                # a class attribute: the names it binds are the class's
                for kid in st.kids:
                    if kid.kind != "name" or kid is st.kids[-1]:
                        self.qexpr(m, kid, loc)
            elif cls and k == "annassign" and st.kids[0].kind == "name":
                # a field: the name is the class's, the annotation and default value the module's
                self.qann(m, st.kids[1], loc)
                for kid in st.kids[2:]:
                    self.qexpr(m, kid, loc)
            elif k == "annassign":
                self.qexpr(m, st.kids[0], loc)
                self.qann(m, st.kids[1], loc)
                for kid in st.kids[2:]:
                    self.qexpr(m, kid, loc)
            elif k == "import" or k == "global":
                for a in st.kids:
                    a.s = self.qname(m, a.s, {})
            elif k != "uimport":
                for kid in st.kids:
                    if kid.kind == "block":
                        self.qstmts(m, kid.kids, loc, False)
                    else:
                        self.qexpr(m, kid, loc)


# ---------------------------------------------------------------- types
# A type is a canonical string: int float bool str None file, list[T], dict[K,V],
# tuple[A,B], or a class name. LLVM view: i64, double, i1, void, everything else ptr.
HEX = "0123456789ABCDEF"
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
    "os.system(str)": "pys_system:int",
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
    "time.sleep(bool)": "pys_sleep_int:None",
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
for _k in "sqrt sin cos tan asin acos atan sinh cosh tanh exp log log2 log10 fabs log1p expm1 exp2 cbrt degrees radians".split():
    CALLS[f"math.{_k}(float)"] = f"pys_m_{_k}:float"
for _k in "pow atan2 hypot fmod copysign".split():
    CALLS[f"math.{_k}(float,float)"] = f"pys_m_{_k}:float"
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
           "NewType assert_never reveal_type dataclass_transform Pattern Match Text ByteString").split():
    TYPING[_k] = True
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
# node kinds the parser accepts but code generation rejects, where it compiles them: an
# imported module may use them in functions the program never calls
UNSUPPORTED: dict[str, str] = {
    "try": "'try' statements are not supported", "nonlocal": "'nonlocal' is not supported",
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
# encoding= names of UTF-8 (1) and Latin-1 (2) as CPython's codec lookup finds them (see codec()):
# a str holds the file's bytes either way, which is what CPython's str holds for a Latin-1 file
CODECS: dict[str, int] = {}
for _k in "utf8 u8 utf utf8_ucs2 utf8_ucs4 cp65001".split():
    CODECS[_k] = 1
for _k in "latin1 latin l1 iso8859_1 iso_8859_1 iso_8859_1_1987 iso_ir_100 iso8859 8859 cp819 ibm819 csisolatin1".split():
    CODECS[_k] = 2


def codec(e: str) -> int:
    # 1 UTF-8, 2 Latin-1, 0 another (runtime.c's codec()): the name normalized (lowercase; a run of
    # characters other than ASCII letters, digits and "." is one "_" between them) is an alias, or
    # one with "." read as "_", or the codec's module name
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
    if n.find(".") >= 0:
        return CODECS.get(n.replace(".", "_"), 0)
    return 1 if n == "utf_8" else 2 if n == "latin_1" else CODECS.get(n, 0)
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


def lt(t: str) -> str:
    if t == "int":
        return "i64"
    if t == "float":
        return "double"
    if t == "bool":
        return "i1"
    if t == "None":
        return "void"
    return "ptr"


def rtt(t: str) -> str:
    return "i64" if t == "bool" else lt(t)


def tname(t: str) -> str:
    # the CPython name of a type, for error messages
    if t == "None":
        return "NoneType"
    if t == "file":
        return "TextIOWrapper"
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
    if t.kind == "name":
        out.append(t.s)
    elif t.kind == "tuple":
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
    # Python's rule: a name assigned anywhere in a function is local to it
    for st in body:
        targets(st, out)
        for kid in st.kids:
            if kid.kind == "block":
                collect(kid.kids, out)

def top_bindings(body: list[Node]) -> dict[str, int]:
    # how many module-level statements bind each name (imports aside)
    count: dict[str, int] = {}
    for st in body:
        names: dict[str, bool] = {}
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            names[st.s] = True
        elif st.kind != "import":
            collect([st], names)
        for nm in names:
            count[nm] = count.get(nm, 0) + 1
    return count


def global_order(body: list[Node], seen: dict[str, str], decl: dict[str, bool]) -> None:
    # CPython's symbol-table errors for global statements in a function body: a name it
    # declares global must not be assigned or used before, nor annotated
    for st in body:
        if st.kind == "global":
            for g in st.kids:
                if g.s in seen:
                    fail(f"name '{g.s}' is {seen[g.s]} global declaration", st.line)
            continue
        if st.kind == "annassign" and st.kids[0].kind == "name" and st.kids[0].s in decl:
            fail(f"annotated name '{st.kids[0].s}' can't be global", st.line)
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            seen[st.s] = "assigned to before"
            continue
        asg: dict[str, bool] = {}
        compound = False
        for kid in st.kids:
            if kid.kind == "block":
                compound = True
        if not compound:
            collect([st], asg)
        elif st.kind == "for" or st.kind == "with":
            names: list[str] = []
            for kid in st.kids:
                if kid is st.kids[0] and st.kind == "for":
                    names_in(kid, names)
                elif kid.kind == "withitem" and len(kid.kids) == 2:
                    names_in(kid.kids[1], names)
            for nm in names:
                asg[nm] = True
        for kid in st.kids:
            if kid.kind != "block":
                uses(kid, seen)
        for nm in asg:
            if nm == "__debug__":
                fail("cannot assign to __debug__", st.line)
            seen[nm] = "assigned to before"
        for kid in st.kids:
            if kid.kind == "block":
                global_order(kid.kids, seen, decl)


def uses(n: Node, seen: dict[str, str]) -> None:
    # the names expression n reads, as global_order records them
    if n.kind == "name" and n.s not in seen:
        seen[n.s] = "used prior to"
    if n.kind == "lambda":
        return
    for k in n.kids:
        uses(k, seen)


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
    return out


def deleted(body: list[Node], out: dict[str, bool]) -> None:
    # the names that del statements in body unbind (not in functions)
    for st in body:
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
                    deleted(kid.kids, out)


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


def local_names(body: list[Node], out: dict[str, bool]) -> None:
    # a function's locals: the names it assigns, but not a qualified name (M$x), which an
    # assignment to a module's attribute (M.x = ...) or a global M declares makes
    asg: dict[str, bool] = {}
    collect(body, asg)
    for nm in asg:
        if "$" not in nm:
            out[nm] = True


def globals_in(body: list[Node], out: dict[str, bool]) -> None:
    for st in body:
        if st.kind == "global":
            for nm in st.kids:
                out[nm.s] = True
        for kid in st.kids:
            if kid.kind == "block":
                globals_in(kid.kids, out)


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
        self.inst = False  # a template's function, compiled for one list of argument types
        self.vararg = -1  # the index of a template's *args parameter (a tuple of the extra arguments), or -1
        self.varelem = ""  # its annotation (the type of each extra argument), or ""


class Frame:
    # the code generator's state for one function, saved while it compiles another
    def __init__(self, curfn: FnInfo):
        self.body: list[str] = []
        self.allocas: list[str] = []
        self.ltype: dict[str, str] = {}
        self.lreg: dict[str, str] = {}
        self.gdecl: dict[str, bool] = {}
        self.assigned: dict[str, bool] = {}
        self.compvars: dict[str, int] = {}
        self.loops: list[str] = []
        self.withs: list[str] = []
        self.wdepth: list[int] = []
        self.lcs: list[str] = []
        self.lct: list[str] = []
        self.ret = ""
        self.retann = False
        self.cold: dict[str, str] = {}
        self.nn: dict[str, bool] = {}
        self.selfname = ""
        self.uflags: dict[str, bool] = {}
        self.lflag: dict[str, str] = {}
        self.nonevars: dict[str, bool] = {}
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
        self.ftypes: dict[str, str] = {}
        self.fdefault: dict[str, Node] = {}
        self.fglob: dict[str, str] = {}
        self.fflag: dict[str, int] = {}  # field -> index of its "is assigned" flag in the struct
        self.methods: dict[str, FnInfo] = {}
        self.mod = ""
        self.bad = ""  # why a class of an imported module cannot be compiled: an error where it is used


class Flow:
    # definite assignment over one scope: which reads may find their variable unassigned
    def __init__(self, tracked: dict[str, bool], defd: dict[str, bool], top: bool):
        self.tracked = tracked
        self.defd = defd  # names assigned on every path to here; " dead" marks unreachable code
        self.top = top
        self.brks: list[dict[str, bool]] = []
        self.marks: dict[str, bool] = {}
        self.call: dict[str, bool] = {}
        self.called = False
        # field mode, over __init__: which fields may be seen unassigned (".f" in defd = assigned)
        self.me = ""
        self.fields: list[str] = []
        self.unsafe: dict[str, bool] = {}

    def exposed(self) -> None:
        # self escapes or __init__ returns: fields not assigned yet may be read unassigned
        if " dead" not in self.defd:
            for f in self.fields:
                if "." + f not in self.defd:
                    self.unsafe[f] = True

    def join(self, other: dict[str, bool]) -> None:
        if " dead" in other:
            return
        if " dead" in self.defd:
            self.defd = dict(other)
            return
        out: dict[str, bool] = {}
        for k in self.defd:
            if k in other:
                out[k] = True
        self.defd = out


# ---------------------------------------------------------------- code generator
class Gen:
    def __init__(self):
        self.classes: dict[str, ClassInfo] = {}
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
        self.decls: dict[str, str] = {}
        self.out: list[str] = []
        self.body: list[str] = []
        self.allocas: list[str] = []
        self.ltype: dict[str, str] = {}
        self.lreg: dict[str, str] = {}
        self.gdecl: dict[str, bool] = {}
        self.assigned: dict[str, bool] = {}
        self.compvars: dict[str, int] = {}
        self.loops: list[str] = []
        self.withs: list[str] = []  # files of the enclosing with blocks, closed when the code leaves them
        self.wdepth: list[int] = []  # len(withs) when each enclosing loop began
        self.lcs: list[str] = []
        self.lct: list[str] = []
        self.ret = "None"
        self.retann = False
        self.cold: dict[str, str] = {}
        self.nn: dict[str, bool] = {}
        self.selfname = ""
        self.lazy: dict[str, FnInfo] = {}
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
        self.nonevars: dict[str, bool] = {}  # parameters of a template's function whose argument is None
        self.branch = 0  # how many if branches and loop bodies enclose the code being compiled
        self.making: list[str] = []  # the template functions being compiled, each with its call site
        self.unsupported: dict[str, str] = {}  # classes of imported modules that cannot be compiled: why
        self.noneglobals: dict[str, bool] = {}  # module globals of imported modules that are always None
        # an imported module's globals (and defs and classes) that other code may find unbound:
        # not assigned on every path through its module code, or before an import that may run
        # code calling back into the module
        self.late: dict[str, bool] = {}
        self.lib = False  # declaring an imported module's function: what it cannot compile is an error only where it is called
        self.deps: dict[str, str] = {}  # the modules each module's top-level code imports, space-separated
        self.flowmod = ""
        self.elsekids: list[Node] = []  # the body of a for/while ... else loop being compiled
        self.elsebrk = ""  # and the label after its else block
        # empty [] and {} assigned to a variable without a type: its type has "?" until a use shows
        # what the container holds (see fill); a dict's key kind is a placeholder in the IR until then
        self.allowq = False  # the read being compiled may see such a type (len(), a truth test)
        self.lkk: dict[str, str] = {}  # a local's placeholders, space-separated
        self.gkk: dict[str, str] = {}  # a global's
        self.keykind: dict[str, str] = {}  # placeholder -> 1 (str keys) or 0 (int keys)
        self.nkeys = 0

    # ---- emission helpers
    def err(self, msg: str) -> None:
        if len(self.making) > 0:
            # an error in a template's function: say which call made it compile
            for i in range(len(self.making) - 1, -1, -1):
                msg += ("; " if i < len(self.making) - 1 else " (") + self.making[i]
            msg += ")"
        fail(msg, self.line)

    def save(self) -> Frame:
        fr = Frame(self.curfn)
        fr.body = self.body
        fr.allocas = self.allocas
        fr.ltype = self.ltype
        fr.lreg = self.lreg
        fr.gdecl = self.gdecl
        fr.assigned = self.assigned
        fr.compvars = self.compvars
        fr.loops = self.loops
        fr.withs = self.withs
        fr.wdepth = self.wdepth
        fr.lcs = self.lcs
        fr.lct = self.lct
        fr.ret = self.ret
        fr.retann = self.retann
        fr.cold = self.cold
        fr.nn = self.nn
        fr.selfname = self.selfname
        fr.uflags = self.uflags
        fr.lflag = self.lflag
        fr.nonevars = self.nonevars
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
        self.body = fr.body
        self.allocas = fr.allocas
        self.ltype = fr.ltype
        self.lreg = fr.lreg
        self.gdecl = fr.gdecl
        self.assigned = fr.assigned
        self.compvars = fr.compvars
        self.loops = fr.loops
        self.withs = fr.withs
        self.wdepth = fr.wdepth
        self.lcs = fr.lcs
        self.lct = fr.lct
        self.ret = fr.ret
        self.retann = fr.retann
        self.cold = fr.cold
        self.nn = fr.nn
        self.selfname = fr.selfname
        self.uflags = fr.uflags
        self.lflag = fr.lflag
        self.nonevars = fr.nonevars
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
        if self.term:
            self.place(self.label())
        self.body.append("  " + s)

    def ins(self, s: str) -> str:
        r = self.tmp()
        self.emit(f"{r} = {s}")
        return r

    def place(self, l: str) -> None:
        if not self.term:
            self.body.append(f"  br label %{l}")
        self.body.append(l + ":")
        self.cur = l
        self.term = False

    def br(self, l: str) -> None:
        if not self.term:
            self.body.append(f"  br label %{l}")
            self.term = True

    def cbr(self, c: str, a: str, b: str) -> None:
        self.emit(f"br i1 {c}, label %{a}, label %{b}")
        self.term = True

    def rt(self, name: str, ret: str, args: list[str]) -> str:
        tys: list[str] = []
        for a in args:
            tys.append(a[: a.find(" ")])
        self.decls[name] = f"declare {ret} @{name}({', '.join(tys)})"
        call = f"call {ret} @{name}({', '.join(args)})"
        if ret == "void":
            self.emit(call)
            return ""
        return self.ins(call)

    def checked(self, op: str, a: str, b: str) -> list[str]:
        # [result, overflowed] of llvm.<op>.with.overflow.i64
        f = f"llvm.{op}.with.overflow.i64"
        self.decls[f] = f"declare {{i64, i1}} @{f}(i64, i64)"
        r = self.ins(f"call {{i64, i1}} @{f}(i64 {a}, i64 {b})")
        return [self.ins(f"extractvalue {{i64, i1}} {r}, 0"), self.ins(f"extractvalue {{i64, i1}} {r}, 1")]

    def guard(self, bad: str, msg: str) -> None:
        # if bad, jump to a block (one per function and message) that raises msg ("Kind: text")
        if msg not in self.cold:
            self.cold[msg] = self.label()
        l = self.label()
        self.cbr(bad, self.cold[msg], l)
        self.place(l)

    def iop(self, op: str, a: str, b: str) -> str:
        # checked 64-bit arithmetic: overflow raises OverflowError (CPython would grow the int)
        r = self.checked(op, a, b)
        self.guard(r[1], "OverflowError: integer result does not fit in 64 bits")
        return r[0]

    def notnone(self, v: Val, msg: str) -> None:
        # objects may be None (null); using one that is raises like CPython
        if v.t in self.classes and v.v not in self.nn:
            self.guard(self.ins(f"icmp eq ptr {v.v}, null"), msg)

    def sconst(self, s: str) -> str:
        if s in self.strs:
            return self.strs[s]
        name = f"@s.{len(self.strs)}"
        self.strs[s] = name
        n = len(s) + 1
        self.consts.append(f'{name} = private unnamed_addr constant {{i64, [{n} x i8]}} {{i64 {n - 1}, [{n} x i8] c"{llstr(s)}\\00"}}, align 8')
        return name

    def alloca(self, t: str, name: str) -> str:
        if t == "None":
            self.err(f"cannot infer the type of '{name}' from None; annotate it with an optional class type ({name}: C | None)")
        if t == "":
            self.err(f"cannot infer the type of '{name}'; add a type annotation")
        self.n += 1
        r = f"%{name or 'h'}.{self.n}"
        self.allocas.append(f"  {r} = alloca {lt(t)}")
        self.allocas.append(f"  store {lt(t)} zeroinitializer, ptr {r}")
        if name != "":
            self.ltype[name] = t
            self.lreg[name] = r
            if name in self.uflags and name not in self.compvars:
                # "is assigned" flag for a local that some read may find unassigned
                self.lflag[name] = f"%{name}.def.{self.n}"
                self.allocas.append(f"  {self.lflag[name]} = alloca i1")
                self.allocas.append(f"  store i1 false, ptr {self.lflag[name]}")
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
        return t in self.classes and len(self.classes[t].node.kids) > 1

    def isnum(self, t: str) -> bool:
        return t == "int" or t == "float" or t == "bool"

    def isref(self, t: str) -> bool:
        return t == "None" or lt(t) == "ptr"

    def coerce(self, v: Val, t: str) -> Val:
        if v.t == t:
            return v
        if v.t == "None" and t in self.classes:
            return Val("null", t)
        hint = " (write a float literal like 1.0, or use float())" if t == "float" and v.t == "int" else ""
        self.err(f"expected {t}, got {v.t}{hint}")
        return v

    def desc(self, t: str) -> str:
        # type descriptor for the runtime's generic repr/equality/ordering
        if t == "int":
            return "i"
        if t == "float":
            return "f"
        if t == "bool":
            return "b"
        if t == "str":
            return "s"
        if is_list(t):
            return "L" + self.desc(elem(t))
        if is_dict(t):
            a = targs(t)
            return "D" + self.desc(a[0]) + self.desc(a[1])
        if is_tuple(t):
            a = targs(t)
            if len(a) > 9:
                self.err("tuples are limited to 9 elements")
            return "T" + str(len(a)) + "".join([self.desc(x) for x in a])
        if t in self.classes:
            # O<id>: the runtime calls back into pys_obj_eq/lt/repr, which dispatch on the id
            if t not in self.ocls:
                self.ocls[t] = len(self.ocls)
            return f"O{self.ocls[t]:03d}"
        self.err(f"{tname(t)} values cannot be compared or printed")
        return ""

    # ---- types and declarations
    def typeof(self, n: Node) -> str:
        k = n.kind
        if k == "None":
            return "None"
        if k == "str":
            return self.typeof(self.parse_expr(n.s))
        if k == "name":
            s = n.s
            if s == "int" or s == "float" or s == "bool" or s == "str" or s in self.classes:
                return s
            if self.typing_name(s) == "TextIO":
                return "file"
            if s in self.unsupported:
                self.err(self.unsupported[s])
        elif k == "attr" and self.typing_attr(n) == "TextIO":
            return "file"
        elif k == "binop" and n.s == "|" and n.kids[1].kind == "None":
            return self.opt(self.typeof(n.kids[0]))
        elif k == "index" and (n.kids[0].kind == "name" or n.kids[0].kind == "attr"):
            base = n.kids[0].s
            if n.kids[0].kind == "attr":
                base = self.typing_attr(n.kids[0]).lower()  # typing.List[int]
            elif base != "list" and base != "dict" and base != "tuple":
                base = self.typing_name(base).lower()
            a: list[Node] = n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]
            ts = [self.typeof(x) for x in a]
            if base == "list" and len(ts) == 1:
                return f"list[{ts[0]}]"
            if base == "dict" and len(ts) == 2:
                if ts[0] != "int" and ts[0] != "str":
                    self.err("dict keys must be int or str")
                return f"dict[{ts[0]},{ts[1]}]"
            if base == "tuple" and len(ts) > 0:
                return f"tuple[{','.join(ts)}]"
            if base == "optional" and len(ts) == 1:
                return self.opt(ts[0])
        self.err("unsupported type annotation")
        return ""

    def ann_problem(self, n: Node, ret: bool) -> str:
        # why typeof(n) would fail, as far as its form shows ("" for a string, a forward
        # reference, which is checked where it is used)
        k = n.kind
        if k == "None":
            return "" if ret else "None is only supported as a return type; annotate an optional object as C | None"
        if k == "str":
            return ""
        if k == "name":
            if n.s == "int" or n.s == "float" or n.s == "bool" or n.s == "str" or n.s in self.classes or self.imported(n.s) == "typing.TextIO":
                return ""
            return self.unsupported[n.s] if n.s in self.unsupported else "unsupported type annotation"
        if k == "binop" and n.s == "|" and n.kids[1].kind == "None":
            return self.ann_problem(n.kids[0], False)
        if k == "attr" and self.typing_attr(n) == "TextIO":
            return ""
        if k == "index" and (n.kids[0].kind == "name" or (n.kids[0].kind == "attr" and self.typing_attr(n.kids[0]) != "")):
            for x in n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]:
                r = self.ann_problem(x, False)
                if r != "":
                    return r
            return ""
        return "unsupported type annotation"

    def vtype(self, n: Node) -> str:
        # the annotation of a variable, parameter or field: None alone is only a return type
        t = self.typeof(n)
        if t == "None":
            self.err("None is only supported as a return type; annotate an optional object as C | None")
        return t

    def typing_attr(self, n: Node) -> str:
        # the typing name an attribute denotes (typing.Optional, t.List after import typing as t), or ""
        p = ""
        while n.kind == "attr":
            p = "." + n.s + p
            n = n.kids[0]
        p = self.imported(n.s + p) if n.kind == "name" else ""
        return p[7:] if p.startswith("typing.") else ""

    def typing_name(self, s: str) -> str:
        # List/Dict/Tuple/Optional/TextIO must come from typing, unless annotations are never
        # evaluated (from __future__ import annotations)
        if self.imported(s).startswith("typing."):
            return self.imported(s)[7:]
        if s in TYPING and "__future__.annotations" in self.imports.values():
            return s
        if s in TYPING:
            self.err(f"name '{s}' is not defined (import it from typing)")
        return ""

    def opt(self, t: str) -> str:
        if t not in self.classes:
            self.err(f"None/Optional is only supported for class types, not {t}")
        return t

    def declare_fn(self, d: Node, cls: str) -> FnInfo:
        # a function or method. A module-level function with a parameter that has no annotation
        # is a template: a call compiles it, once per list of argument types, for those types
        # (see instance), and what cannot be compiled in it is an error only then
        self.line = d.line
        f = FnInfo(d.s, f"@f.{d.s}" if cls == "" else f"@m.{cls}.{d.s}", d, cls)
        ps = d.kids[0].kids
        deco = ""
        for x in d.kids[3:]:
            if x.s != "async" and deco == "":
                deco = x.s
        if deco != "" and not self.lib:
            # (CPython applies a decorator when the def runs, called or not)
            self.err(f"unsupported decorator @{deco}")
        if cls != "" and len(ps) == 0:
            self.err(f"method '{d.s}' of class '{cls}' must take self as its first parameter")
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
            if i == 0 and cls != "":
                f.ptypes.append(cls)
            elif p.kids[0].kind == "noann":
                if not f.generic:
                    self.err(f"parameter '{p.s}' of '{d.s}' needs a type annotation")
                f.ptypes.append("")
            elif self.lib and self.ann_problem(p.kids[0], False) != "":
                bad = self.ann_problem(p.kids[0], False)
                f.ptypes.append("int")
            else:
                f.ptypes.append(self.vtype(p.kids[0]))
        if int(marks[0]) == len(ps) and len(ps) > 0:
            f.posonly = len(f.params)  # def f(a, b, /)
        if f.npos < 0:
            f.npos = len(f.params)
        if f.vararg >= 0:
            f.npos = f.vararg
        if len(d.kids) > 3:
            bad = f"unsupported decorator @{deco}" if deco != "" else "async functions are not supported"
        if bad == "" and has_kind(d.kids[2], "yield"):
            bad = UNSUPPORTED["yield"]  # a generator function
        if bad == "" and self.lib and d.kids[1].kind != "noann":
            bad = self.ann_problem(d.kids[1], True)
        if bad != "" and not f.generic and not self.lib:
            self.err(bad)
        f.bad = bad
        if bad != "" and self.lib:
            f.ret = "None"
        elif d.kids[1].kind != "noann":
            f.ret = self.typeof(d.kids[1])
        elif f.generic:
            f.ret = ""
        return f

    def add_field(self, ci: ClassInfo, name: str, t: str) -> None:
        if name in ci.ftypes:
            if ci.ftypes[name] != t:
                self.err(f"field '{name}' redeclared with a different type")
            return
        ci.fields.append(name)
        ci.ftypes[name] = t

    def declare_fields(self, ci: ClassInfo) -> None:
        noann = mk("noann", "", ci.node.line, [])
        last = ""
        for st in ci.node.kids[0].kids:
            self.line = st.line
            if st.kind == "annassign" and st.kids[0].kind == "name" and ci.mod != "" and self.ann_problem(st.kids[1], False) != "":
                # an imported module's class: an error only where the program uses it
                ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {self.ann_problem(st.kids[1], False)}"
                self.add_field(ci, st.kids[0].s, "int")
            elif st.kind == "annassign" and st.kids[0].kind == "name":
                self.add_field(ci, st.kids[0].s, self.vtype(st.kids[1]))
                if len(st.kids) == 3:
                    ci.fdefault[st.kids[0].s] = st.kids[2]
                    last = st.kids[0].s
                elif last != "" and self.is_dc(ci.name):
                    self.err(f"non-default argument '{st.kids[0].s}' follows default argument '{last}'")
            elif st.kind != "def" and st.kind != "pass" and not (st.kind == "expr" and st.kids[0].kind == "str"):
                self.err("a class body may only contain annotated fields and methods")
        if self.is_dc(ci.name):
            self.dc_methods(ci)
        if "__init__" in ci.methods:
            f = ci.methods["__init__"]
            self.scan_fields(ci, f, f.node.kids[2].kids)
            return
        # synthesize __init__: @dataclass takes every field as a parameter
        body: list[Node] = []
        d = mk("def", "__init__", ci.node.line, [noann, noann, mk("block", "", ci.node.line, body)])
        f = FnInfo("__init__", f"@m.{ci.name}.__init__", d, ci.name)
        f.params.append("self")
        f.ptypes.append(ci.name)
        f.defaults.append(noann)
        f.dglob.append("")
        if len(ci.node.kids) > 1:
            for fl in ci.fields:
                f.params.append(fl)
                f.ptypes.append(ci.ftypes[fl])
                f.defaults.append(ci.fdefault[fl] if fl in ci.fdefault else noann)
                f.dglob.append("")
                me = mk("name", "self", d.line, [])
                body.append(mk("assign", "", d.line, [mk("attr", fl, d.line, [me]), mk("name", fl, d.line, [])]))
        ci.methods["__init__"] = f

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
            self.synth(ci, "__repr__", "str", [mk("if", "", line, [mk("unary", "not", line, [enter]), busy, mk("block", "", line, [])]),
                                              mk("assign", "", line, [r, mk("fstr", "", line, parts)]),
                                              mk("expr", "", line, [mk("call", "", line, [mk("name", "__pys_repr_leave", line, []), me])]),
                                              mk("return", "", line, [r])])
        if "__eq__" not in ci.methods:
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
            if (k == "assign" or k == "annassign") and st.kids[0].kind == "attr" and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == "self":
                name = st.kids[0].s
                if name not in ci.ftypes:
                    why = self.ann_problem(st.kids[1], False) if k == "annassign" and ci.mod != "" else ""
                    t = "" if why != "" else self.vtype(st.kids[1]) if k == "annassign" else self.guess(st.kids[-1], f)
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

    def guess(self, e: Node, f: FnInfo) -> str:
        k = e.kind
        if k == "int" or k == "float" or k == "str":
            return k
        if k == "True" or k == "False":
            return "bool"
        if k == "fstr":
            return "str"
        if k == "unary" and e.s == "-":
            return self.guess(e.kids[0], f)
        if k == "name" and e.s in f.params:
            return f.ptypes[f.params.index(e.s)]
        if k == "call" and e.kids[0].kind == "name":
            c = e.kids[0].s
            if c in self.classes:
                return c
            if c in self.funcs:
                return self.funcs[c].ret
            if c == "str" or c == "int" or c == "float" or c == "bool":
                return c
            if c == "len" or c == "ord":
                return "int"
            if c == "input" or c == "repr" or c == "chr" or c == "ascii":
                return "str"
            if c == "open":
                return "file"
        me = f.params[0] if f.cls != "" else ""
        if k == "attr" and e.kids[0].kind == "name" and e.kids[0].s == me:
            return self.classes[f.cls].ftypes.get(e.s, "")
        if k == "call" and e.kids[0].kind == "attr" and e.kids[0].kids[0].kind == "name" and e.kids[0].kids[0].s == me:
            ms = self.classes[f.cls].methods
            return ms[e.kids[0].s].ret if e.kids[0].s in ms else ""
        if k == "cmp" or (k == "unary" and e.s == "not"):
            return "bool"
        if k == "ifexp":
            return self.guess(e.kids[1], f)
        if k == "list" and len(e.kids) > 0:
            t = self.guess(e.kids[0], f)
            return f"list[{t}]" if t != "" else ""
        if k == "binop":
            a = self.guess(e.kids[0], f)
            b = self.guess(e.kids[1], f)
            if self.isnum(a) and self.isnum(b):
                if e.s == "/" or a == "float" or b == "float":
                    return "float"
                return "bool" if a == "bool" and b == "bool" and e.s in IOPS else "int"
            if a == b and (a == "str" or is_list(a)):
                return a
        return ""

    def field(self, o: Val, name: str, store: bool = False) -> Val:
        if o.t not in self.classes:
            base = "list" if is_list(o.t) else "dict" if is_dict(o.t) else o.t
            if base + "." + name in METHODS:
                self.err(f"{tname(o.t)}.{name} is a method: call it, {name}(...) (methods are not values)")
            self.err(f"type {o.t} has no attribute '{name}'")
        ci = self.classes[o.t]
        if name not in ci.ftypes:
            if name in ci.methods:
                self.err(f"{o.t}.{name} is a method: call it, {name}(...) (methods are not values)")
            self.err(f"'{o.t}' object has no attribute '{name}'")
        extra = " and no __dict__ for setting new attributes" if store else ""
        self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{name}'{extra}")
        i = ci.fields.index(name)
        return Val(self.ins(f"getelementptr %C.{o.t}, ptr {o.v}, i32 0, i32 {i}"), ci.ftypes[name])

    def getfield(self, o: Val, p: Val, name: str) -> Val:
        # load a field (p = self.field(o, name)); a field __init__ may leave unassigned is checked
        ci = self.classes[o.t]
        if name in ci.fflag:
            f = self.ins(f"getelementptr %C.{o.t}, ptr {o.v}, i32 0, i32 {ci.fflag[name]}")
            self.guard(self.ins(f"xor i1 {self.ins(f'load i1, ptr {f}')}, true"), f"AttributeError: '{tname(o.t)}' object has no attribute '{name}'")
        return Val(self.ins(f"load {lt(p.t)}, ptr {p.v}"), p.t)

    def setfield(self, o: Val, p: Val, name: str, v: Val) -> None:
        self.emit(f"store {lt(p.t)} {self.coerce(v, p.t).v}, ptr {p.v}")
        ci = self.classes[o.t]
        if name in ci.fflag:
            self.emit(f"store i1 true, ptr {self.ins(f'getelementptr %C.{o.t}, ptr {o.v}, i32 0, i32 {ci.fflag[name]}')}")

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

    def load_name(self, name: str) -> Val:
        if (name in self.nonevars or name in self.noneglobals) and name not in self.ltype:
            return Val("null", "None")
        if "?" in self.qtype(name) and not self.allowq and self.lookahead(name) == "":
            t = self.qtype(name)
            self.err(f"cannot infer the type of '{name}', an empty {'list' if is_list(t) else 'dict'} so far: annotate it ({name}: {'list[T] = []' if is_list(t) else 'dict[K, V] = {}'})")
        if name in self.ltype:
            t = self.ltype[name]
            r = self.ins(f"load {lt(t)}, ptr {self.lreg[name]}")
            if name == self.selfname and name not in self.compvars:
                self.nn[r] = True
            return Val(r, t)
        if name in self.assigned and name not in self.gdecl:
            self.err(f"local variable '{name}' is read before its first assignment; declare it first ({name}: T)")
        if name in self.gtypes:
            t = self.gtypes[name]
            return Val(self.ins(f"load {lt(t)}, ptr @g.{name}"), t)
        if name == "__name__":
            return Val(self.sconst("__main__"), "str")
        if name in self.aliases:
            return self.modattr(self.aliases[name])
        if name in self.funcs:
            self.err(f"function '{name}' cannot be used as a value")
        if name in self.classes:
            self.err(f"class '{name}' cannot be used as a value (class attributes are read through an instance)")
        if name in self.fglobals:
            self.err(f"name '{name}' is not defined yet here: a function assigns it, so declare it at module level first ({name}: T)")
        if name in self.unsupported:
            self.err(self.unsupported[name])
        if name in PYBUILTINS:
            self.err(f"the builtin '{name}' cannot be used as a value (not supported)")
        self.err(f"name '{short(name)}' is not defined")
        return Val("", "")

    def read(self, n: Node) -> Val:
        # a variable read; if flow analysis found it may be unassigned, check at run time
        name = n.s
        if n.chk and name in self.ltype:
            if name in self.lflag and name not in self.compvars:
                bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr {self.lflag[name]}')}, true")
                self.guard(bad, f"UnboundLocalError: cannot access local variable '{name}' where it is not associated with a value")
        elif (n.chk or self.foreign(name)) and name in self.gflag and name in self.gtypes:
            bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{name}.def')}, true")
            self.guard(bad, self.unbound(name))
        return self.load_name(name)

    def foreign(self, name: str) -> bool:
        # another module's global that may be unbound when this code reads it
        return name in self.late and owner(name) != self.curfn.mod

    def unbound(self, name: str) -> str:
        # what CPython raises for reading name unbound (as M.x from another module)
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

    def empty(self, kind: str, name: str) -> Val:
        # [] or {} assigned to a variable without a type: the first use that shows what it holds
        # gives the variable its type (fill, refine); until then only len() and truth tests read it
        if kind == "list":
            return Val(self.rt("pys_list_new", "ptr", ["i64 0"]), "list[?]")
        self.nkeys += 1
        tok = f"<keys{self.nkeys}>"
        if self.is_global(name):
            self.gkk[name] = self.gkk.get(name, "") + " " + tok
        else:
            self.lkk[name] = self.lkk.get(name, "") + " " + tok
        return Val(self.rt("pys_dict_new", "ptr", [f"i64 {tok}", "i64 0"]), "dict[?,?]")

    def refine(self, name: str, t: str) -> None:
        # the variable holding an empty list or dict gets the type its first use shows
        if "?" in t or "None" in targs(t):
            self.err(f"cannot infer the type of '{name}' from this use; annotate it")
        toks = ""
        if name in self.ltype:
            self.ltype[name] = t
            toks = self.lkk.pop(name, "")
        else:
            self.gtypes[name] = t
            toks = self.gkk.pop(name, "")
        if is_dict(t):
            if targs(t)[0] != "int" and targs(t)[0] != "str":
                self.err("dict keys must be int or str")
            for tok in toks.split():
                self.keykind[tok] = "1" if targs(t)[0] == "str" else "0"

    def lookahead(self, name: str) -> str:
        # an empty list or dict read before the code that fills it: the first use in this
        # function's source that shows its items (an append, d[k] = v, ...) decides its type now,
        # if the item expression reads only variables whose types are already known here; ""
        # if there is no such use
        found: list[Node] = []
        self.fills(self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids, name, found)
        if len(found) == 0:
            return ""
        t = self.qtype(name)
        e = found[-1]
        for x in found:
            if not self.typed_now(x):
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
        self.refine(name, r)
        return r

    def fills(self, body: list[Node], name: str, found: list[Node]) -> None:
        # the first statement in body (searched in order, into blocks) that fills variable name:
        # found gets [key or omit, item]
        for st in body:
            if len(found) > 0:
                return
            if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
                continue
            k = st.kind
            if (k == "assign" or k == "augassign") and st.kids[0].kind == "index" and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == name and k == "assign":
                found.append(st.kids[0].kids[1])
                found.append(st.kids[-1])
            elif k == "augassign" and st.kids[0].kind == "name" and st.kids[0].s == name and st.s == "+":
                found.append(mk("omit", "", st.line, []))
                found.append(st.kids[1])
            elif k == "if" and self.static(st.kids[0]) >= 0:
                # a test decided here: only the branch that runs
                self.fills(st.kids[1 if self.static(st.kids[0]) == 1 else 2].kids, name, found)
            else:
                self.fill_calls(st, name, found)
                for kid in st.kids:
                    if kid.kind == "block":
                        self.fills(kid.kids, name, found)

    def fill_calls(self, n: Node, name: str, found: list[Node]) -> None:
        # name.append(v), insert(i, v), extend(xs), setdefault(k, v), get(k, v) anywhere in n
        if len(found) > 0 or n.kind == "block" or n.kind == "listcomp":
            return  # (a comprehension's names are its own)
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
        for kid in n.kids:
            self.fill_calls(kid, name, found)

    def typed_now(self, e: Node) -> bool:
        # can e be compiled here: every variable it reads has its type already
        if e.kind == "name":
            if e.s in self.funcs or e.s in self.classes or e.s in self.aliases:
                return True
            t = self.qtype(e.s)
            if t != "":
                return "?" not in t
            return not (e.s in self.assigned or e.s in self.mvars or e.s in self.nonevars)
        if e.kind == "listcomp" or e.kind == "lambda" or e.kind in UNSUPPORTED:
            return False
        for k in e.kids:
            if not self.typed_now(k):
                return False
        return True

    def dry(self, e: Node) -> str:
        # the type of e, compiled into code that is dropped
        body = self.body
        cur = self.cur
        term = self.term
        self.body = []
        t = self.expr(e, "").t
        self.body = body
        self.cur = cur
        self.term = term
        return t

    def fill(self, n: Node, m: str, args: list[Node]) -> Val:
        # name.append(v), insert(i, v) or extend(xs) on a list, and name.setdefault(k, v) or
        # name.get(k, default) on a dict, whose variable has no type yet: the items decide it
        name = n.s
        self.allowq = True
        o = self.read(n)
        self.allowq = False
        for a in args:
            if a.kind == "kw":
                self.err(f"keyword arguments to {'list' if is_list(o.t) else 'dict'}.{m}() are not supported; pass them by position")
        if is_list(o.t) and (m == "append" or m == "extend" or m == "insert") and len(args) == (2 if m == "insert" else 1):
            i = self.ival(args[0]) if m == "insert" else Val("0", "int")
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
            k = self.expr(args[0], "")
            v = self.expr(args[1], "")
            self.refine(name, f"dict[{k.t},{v.t}]")
            return self.from_slot(self.rt(f"pys_dict_{m}", "i64", [f"ptr {o.v}", "i64 " + self.to_slot(k), "i64 " + self.to_slot(v)]), v.t)
        # any other method: the type a later use shows (or an error), then the method as usual
        return self.method(self.load_name(name), m, args)

    def declare(self, name: str, t: str) -> None:
        if self.is_global(name):
            if name not in self.gtypes:
                self.gtypes[name] = t
                self.global_var(f"@g.{name}", lt(t))
                if name in self.gflag:
                    self.global_var(f"@g.{name}.def", "i1")
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
                if v.t == "None":
                    self.err(f"cannot infer the type of '{name}' from None; annotate it with an optional class type ({name}: C | None)")
                if v.t == "":
                    self.err(f"cannot infer the type of '{name}'; add a type annotation")
                self.declare(name, v.t)
            t = self.gtypes[name]
            if "?" in t and t[:4] == v.t[:4] and "?" not in v.t:
                self.refine(name, v.t)
                t = v.t
            self.emit(f"store {lt(t)} {self.coerce(v, t).v}, ptr @g.{name}")
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
                del self.nonevars[name]
            if name not in self.ltype:
                self.alloca(v.t, name)
            t = self.ltype[name]
            if "?" in t and t[:4] == v.t[:4] and "?" not in v.t:
                self.refine(name, v.t)
                t = v.t
            self.emit(f"store {lt(t)} {self.coerce(v, t).v}, ptr {self.lreg[name]}")
            if name in self.lflag and name not in self.compvars:
                self.emit(f"store i1 true, ptr {self.lflag[name]}")

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
        return ""

    def assign(self, t: Node, v: Val) -> None:
        k = t.kind
        if k == "badattr":
            self.err(t.s)
        if k in UNSUPPORTED:
            self.err(UNSUPPORTED[k])
        if k == "name":
            self.store_name(t.s, v)
        elif k == "attr" and self.dotted(t) != "":
            self.err(f"assigning to {self.dotted(t)} is not supported; change its value in place")
        elif k == "attr":
            o = self.expr(t.kids[0], "")
            self.setfield(o, self.field(o, t.s, True), t.s, v)
        elif k == "index" and t.kids[0].kind == "name" and "?" in self.qtype(t.kids[0].s):
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
            o = self.expr(t.kids[0], "")
            if is_list(o.t):
                ix = self.ival(t.kids[1])
                s = self.to_slot(self.coerce(v, elem(o.t)))
                self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {ix.v}", f"i64 {s}"])
            elif is_dict(o.t):
                kv = targs(o.t)
                key = self.to_slot(self.coerce(self.expr(t.kids[1], kv[0]), kv[0]))
                self.rt("pys_dict_set", "void", [f"ptr {o.v}", f"i64 {key}", "i64 " + self.to_slot(self.coerce(v, kv[1]))])
            else:
                self.err(f"'{o.t}' does not support item assignment")
        elif k == "tuple" and (is_list(v.t) or v.t == "str"):
            # a, b = xs: the length is checked when it runs, as CPython does
            self.rt("pys_unpack_check", "void", [f"i64 {self.ins(f'load i64, ptr {v.v}')}", f"i64 {len(t.kids)}"])
            for i in range(len(t.kids)):
                if v.t == "str":
                    self.assign(t.kids[i], Val(self.rt("pys_str_get", "ptr", [f"ptr {v.v}", f"i64 {i}"]), "str"))
                else:
                    self.assign(t.kids[i], self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {v.v}", f"i64 {i}"]), elem(v.t)))
        elif k == "tuple":
            if not is_tuple(v.t) or len(targs(v.t)) != len(t.kids):
                self.err(f"cannot unpack {v.t} into {len(t.kids)} targets")
            for i in range(len(t.kids)):
                self.assign(t.kids[i], self.tget(v, i))
        else:
            self.err("cannot assign to this expression")

    # ---- functions and the module
    def function(self, f: FnInfo, body: list[Node]) -> None:
        if f.cls != "" and self.classes[f.cls].bad != "":
            self.err(self.classes[f.cls].bad)
        if f.bad != "" and not f.generic:
            self.err(f.bad)
        self.body = []
        self.allocas = []
        self.ltype = {}
        self.lreg = {}
        self.gdecl = {}
        self.assigned = {}
        self.compvars = {}
        self.loops = []
        self.withs = []
        self.wdepth = []
        self.n = 0
        self.cur = "entry"
        self.term = False
        self.ret = f.ret
        self.retann = f.node.kind == "def" and f.node.kids[1].kind != "noann"
        self.cold = {}
        self.nn = {}
        self.selfname = ""
        self.uflags = f.uflags
        self.lflag = {}
        self.lcs = []
        self.lct = []
        self.nonevars = {}
        self.lkk = {}
        self.branch = 0
        self.curfn = f
        self.line = f.node.line
        if not self.modlevel:
            local_names(body, self.assigned)
            globals_in(body, self.gdecl)  # (global holds for the whole function, also from a dead branch)
        ps: list[str] = []
        if f.cls != "":
            # callers check the receiver, so self is never None inside a method
            self.nn["%a0"] = True
            if f.params[0] not in self.assigned:
                self.selfname = f.params[0]
        for i in range(len(f.params)):
            t = f.ptypes[i]
            if t == "None":
                # an argument that is None: the parameter is not passed, and reads of it are None
                self.nonevars[f.params[i]] = True
                continue
            ps.append(f"{lt(t)}{' nonnull' if i == 0 and f.cls != '' else ''} %a{i}")
            self.emit(f"store {lt(t)} %a{i}, ptr {self.alloca(t, f.params[i])}")
        if f.name == "__init__" and f.cls != "" and not (self.is_dc(f.cls) and f.node.kids[0].kind == "noann"):
            # class-body defaults (a synthesized dataclass __init__ assigns every field itself)
            ci = self.classes[f.cls]
            me = Val("%a0", f.cls)
            for fl in ci.fields:
                if fl in ci.fdefault:
                    t = ci.ftypes[fl]
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
            self.emit("ret void")
            self.term = True
            self.place(l2)
            self.emit(f"store i1 true, ptr {done}")
        self.stmts(body)
        if f.ret == "":
            f.ret = "None"  # a template's function without a return statement that has a value
        if f.infer:
            # its returns of None, before it was known what it returns: None for an object
            for i in range(len(self.body)):
                if self.body[i] == "  ret <none>":
                    if f.ret != "None" and f.ret not in self.classes:
                        self.err(f"{short(f.name)}() returns both None and {f.ret}, and None/Optional is only supported for class types")
                    self.body[i] = "  ret void" if f.ret == "None" else "  ret ptr null"
        if not self.term:
            if f.ret == "None":
                self.emit("ret void")
            elif f.infer and f.ret in self.classes:
                self.emit("ret ptr null")  # a template's function that ends without a return: None
            else:
                self.raise_("RuntimeError", self.sconst(f"{short(f.name)}() ended without returning a value"))
        for msg in self.cold:
            self.place(self.cold[msg])
            i = msg.find(": ")
            self.raise_(msg[:i], self.sconst(msg[i + 2 :]))
        self.out.append(f"define internal {lt(f.ret)} {f.ll}({', '.join(ps)}) {{")
        self.out.append("entry:")
        self.out.extend(self.allocas)
        self.out.extend(self.body)
        self.out.append("}")

    def class_problem(self, st: Node) -> str:
        # why a class of an imported module cannot be declared, or "": its methods need
        # annotated parameters, and its body may hold only fields, methods and a docstring
        if len(st.kids) > 2 or (len(st.kids) > 1 and (len(st.kids[1].kids) > 0 or self.imported(st.kids[1].s) != "dataclasses.dataclass")):
            return f"its decorator @{st.kids[1].s} is not supported"
        for b in st.kids[0].kids:
            if b.kind == "def":
                ps = b.kids[0].kids
                if len(b.kids) > 3:
                    return f"method {b.s}() has a decorator"
                if len(ps) == 0:
                    return f"method {b.s}() has no self parameter"
                for i in range(len(ps)):
                    if ps[i].kind != "param":
                        return f"method {b.s}() takes *args or **kwargs"
                    if i > 0 and ps[i].kids[0].kind == "noann":
                        return f"parameter '{ps[i].s}' of method {b.s}() has no type annotation"
            elif not (b.kind == "annassign" and b.kids[0].kind == "name") and b.kind != "pass" and not (b.kind == "expr" and b.kids[0].kind == "str"):
                return "its body holds statements other than fields, methods and a docstring"
        return ""

    def program(self, mods: list[Mod]) -> str:
        # the modules in the order their code may first run, the main program last
        tops: list[list[Node]] = []
        for m in mods:
            self.scan_imports(m.body.kids)
        for m in mods:
            for st in m.body.kids:
                self.line = st.line
                why = ""
                if st.kind == "subclass":
                    why = UNSUPPORTED["subclass"] if st.kids[1].kind != "typeparams" else "generic classes (class C[T]) are not supported"
                elif st.kind == "class" and m.name != "":
                    why = self.class_problem(st)
                if why != "" and m.name == "":
                    self.err(why)
                if why != "":
                    # a class of an imported module that Pystachy cannot compile: an error only
                    # where the program uses it
                    self.unsupported[st.s] = f"class {st.s} is not supported: {why}"
                elif st.kind == "class":
                    if st.s in self.classes:
                        self.err(f"redefinition of class '{st.s}' is not supported")
                    self.classes[st.s] = ClassInfo(st.s, st)
                    self.classes[st.s].mod = m.name
                    if len(st.kids) > 1 and self.imported(st.kids[1].s) == "dataclasses.dataclass" and len(st.kids[1].kids) > 0:
                        self.err("@dataclass(...) with arguments is not supported")
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
                elif st.kind == "subclass" or (st.kind == "class" and st.s not in self.classes):
                    continue
                elif st.kind == "class":
                    for d in st.kids[0].kids:
                        if d.kind == "def":
                            self.line = d.line
                            if d.s in self.classes[st.s].methods:
                                self.err(f"redefinition of method '{st.s}.{d.s}' is not supported")
                            self.lib = m.name != ""
                            self.classes[st.s].methods[d.s] = self.declare_fn(d, st.s)
                            self.lib = False
                            self.classes[st.s].methods[d.s].mod = m.name
                    top.append(mk("cdefaults", st.s, st.line, []))
                else:
                    top.append(st)
            tops.append(top)
        for ci in self.classes.values():
            self.declare_fields(ci)
            for f in ci.methods.values():
                self.check_special(f)
        for m in mods:
            imps: list[str] = []
            all_imports(m.body.kids, imps)
            self.deps[m.name] = " ".join(imps)
        for i in range(len(mods)):
            self.flow_program(tops[i], mods[i].name)
        for nm in self.gflag:
            if nm in self.funcs or nm in self.classes:
                self.global_var(f"@g.{nm}.def", "i1")
        for m in mods:
            if m.name != "":
                # a module global that module code only sets to None (an optional accelerator's
                # fallback, _json = None, or a cache a function fills, _varsub = None) and that is
                # assigned before any read is the constant None; a compiled function that gives
                # it another value is an error
                vals: dict[str, list[Node]] = {}
                none_assigns(m.body.kids, vals)
                for nm in vals:
                    nones = True
                    for v in vals[nm]:
                        if v.kind != "None":
                            nones = False
                    if nones and nm not in self.gflag and nm in self.mvars:
                        self.noneglobals[nm] = True
        for m in mods:
            for st in m.body.kids if m.name != "" else []:
                # an imported module's constants (NAME = literal) are typed before any module code
                # compiles: a module it imports, which imports it back, may read them first
                if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s not in self.gtypes and st.kids[0].s not in self.noneglobals:
                    k = st.kids[1].kind
                    if k == "int" or k == "float" or k == "str":
                        self.declare(st.kids[0].s, k)
                    elif k == "True" or k == "False":
                        self.declare(st.kids[0].s, "bool")
        self.modlevel = True
        for i in range(len(mods)):
            m = mods[i]
            init = FnInfo("<module>", "@init." + m.name if m.name != "" else "@main.init", m.body, "")
            init.mod = m.name
            self.function(init, tops[i])
        self.modlevel = False
        # the functions and methods of imported modules are compiled only if the program calls
        # them, as templates are
        for f in self.funcs.values():
            if f.mod != "" and not f.generic:
                self.lazy[f.ll] = f
            elif not f.generic:
                self.function(f, f.node.kids[2].kids)
        for ci in self.classes.values():
            for f in ci.methods.values():
                if ci.mod != "" and f.ll not in self.lazy:
                    self.lazy[f.ll] = f
                elif f.ll not in self.lazy:
                    self.function(f, f.node.kids[2].kids)
        # generate on demand: dataclass methods that were called, and helpers for classes that
        # appear inside containers (which can make more of both necessary)
        done: dict[str, bool] = {}
        helped: dict[str, bool] = {}
        while True:
            before = len(done) + len(helped)
            for c in [x for x in self.ocls]:
                if c not in helped:
                    helped[c] = True
                    self.obj_helpers(c)
            for f in [x for x in self.lazy.values()]:
                if f.ll in self.called and f.ll not in done:
                    done[f.ll] = True
                    self.function(f, f.node.kids[2].kids)
            if len(done) + len(helped) == before:
                break
        for op in ["eq", "cmp", "repr"]:
            self.dispatch(op)
        for i in range(len(self.out)):
            # the key kind of each dict created empty: what its first use showed (0 if nothing did)
            ln = self.out[i]
            while ln.find("<keys") >= 0:
                a = ln.find("<keys")
                b = ln.find(">", a)
                ln = ln[:a] + self.keykind.get(ln[a : b + 1], "0") + ln[b + 1 :]
            self.out[i] = ln
        hdr: list[str] = ["; generated by pystachy"]
        for ci in self.classes.values():
            ts = [lt(ci.ftypes[x]) for x in ci.fields]
            for _ in ci.fflag:
                ts.append("i1")
            hdr.append(f"%C.{ci.name} = type {{{', '.join(ts)}}}")
        hdr.extend(self.globs)
        roots = ", ".join([f"ptr {g}" for g in self.gcroots])
        hdr.append(f"@pys.roots = private constant [{len(self.gcroots)} x ptr] [{roots}]")
        hdr.extend(self.consts)
        hdr.extend(self.out)
        hdr.extend(self.decls.values())
        # pys_init gets the GC roots: main's frame address bounds the stack scan (it also
        # covers @main.init if inlined here) and the table of pointer-typed globals
        hdr.append("declare void @pys_init(i32, ptr, ptr, ptr, i64)")
        hdr.append("declare void @pys_finish()")
        hdr.append("declare ptr @llvm.frameaddress.p0(i32)")
        hdr.append("define i32 @main(i32 %argc, ptr %argv) {")
        hdr.append("  %sb = call ptr @llvm.frameaddress.p0(i32 0)")
        hdr.append(f"  call void @pys_init(i32 %argc, ptr %argv, ptr %sb, ptr @pys.roots, i64 {len(self.gcroots)})")
        hdr.append("  call void @main.init()")
        hdr.append("  call void @pys_finish()")
        hdr.append("  ret i32 0")
        hdr.append("}")
        return "\n".join(hdr) + "\n"

    # ---- definite assignment, before code generation: CPython raises UnboundLocalError or
    # NameError when a read finds its variable unassigned. Reads that cannot are plain loads;
    # the others (Node.chk) test an "is assigned" flag kept only for the variables they read.
    def flow_program(self, top: list[Node], mod: str) -> None:
        # one module: its top-level code, functions and methods
        self.flowmod = mod
        fns: list[FnInfo] = []
        for f in self.funcs.values():
            if f.mod == mod:
                fns.append(f)
        for ci in self.classes.values():
            for f in ci.methods.values():
                if ci.mod == mod:
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
        for f in self.funcs.values():
            if f.mod == mod:
                gl[f.name] = True
        for ci in self.classes.values():
            if ci.mod == mod:
                gl[ci.name] = True
        mfl = Flow(gl, {}, True)
        self.fl_stmts(mfl, top)
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
            tracked = dict(gl)
            defd: dict[str, bool] = {}
            for nm in loc:
                tracked[nm] = True
            for nm in gl:
                if nm in safe and nm not in dels and (nm not in loc or nm in decl):
                    defd[nm] = True
            for nm in f.params:
                defd[nm] = True
            fl = Flow(tracked, defd, False)
            self.fl_stmts(fl, body)
            for nm in fl.marks:
                if nm in loc and nm not in decl:
                    f.uflags[nm] = True
                else:
                    self.gflag[nm] = True
        for ci in self.classes.values():
            if ci.mod == mod:
                self.fl_fields(ci)

    def fl_fields(self, ci: ClassInfo) -> None:
        # a field that may be read before __init__ assigns it gets an "is assigned" flag, so the
        # read raises AttributeError as in CPython instead of seeing 0 or null
        init = ci.methods["__init__"]
        fl = Flow({}, {}, False)
        for f in ci.fdefault:
            fl.defd["." + f] = True
        fl.fields = ci.fields
        if init.node.kids[0].kind == "noann":
            if not self.is_dc(ci.name):
                fl.exposed()
        else:
            asg: dict[str, bool] = {}
            collect(init.node.kids[2].kids, asg)
            if init.params[0] not in asg:
                # (if __init__ rebinds self, no assignment is known to reach the new object)
                fl.me = init.params[0]
                self.fl_stmts(fl, init.node.kids[2].kids)
            fl.exposed()
        for f in ci.fields:
            if f in fl.unsafe:
                ci.fflag[f] = len(ci.fields) + len(ci.fflag)

    def fl_defaults(self, n: Node) -> list[Node]:
        # the default values a def or class statement evaluates (see hoist)
        out: list[Node] = []
        fs: list[FnInfo] = []
        if n.kind == "defaults":
            fs.append(self.funcs[n.s])
        else:
            ci = self.classes[n.s]
            for fl in ci.fields:
                if fl in ci.fdefault and not is_const(ci.fdefault[fl]):
                    out.append(ci.fdefault[fl])
            for f in ci.methods.values():
                fs.append(f)
        for f in fs:
            for d in f.defaults:
                if not is_const(d):
                    out.append(d)
        return out

    def reaches(self, a: str, b: str, seen: dict[str, bool]) -> bool:
        # may running module a's code import (and so run) module b
        if a == b:
            return True
        if a in seen:
            return False
        seen[a] = True
        for x in self.deps.get(a, "").split():
            if self.reaches(x, b, seen):
                return True
        return False

    def user_call(self, n: Node) -> bool:
        # may running n call a user function, method or constructor? (an import of a user module
        # runs the module's code)
        if n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s in self.funcs or n.kids[0].s in self.classes):
            return True
        if n.kind == "uimport":
            # it runs a module's code, which can call this module's functions only if it imports
            # this module (circular imports)
            for x in n.kids:
                if self.reaches(x.s, self.flowmod, {}):
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
        if fl.top and not fl.called and self.user_call(n):
            fl.called = True
            fl.call = dict(fl.defd)
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
            pre = dict(fl.defd)
            self.fl_stmts(fl, n.kids[1].kids)
            then = fl.defd
            fl.defd = pre
            self.fl_stmts(fl, n.kids[2].kids)
            fl.join(then)
        elif k == "while" or k == "for":
            self.fl_expr(fl, n.kids[0] if k == "while" else n.kids[1])
            dels: dict[str, bool] = {}
            deleted(n.kids[2 if k == "for" else 1].kids, dels)
            for nm in dels:
                if nm in fl.defd:
                    del fl.defd[nm]  # (a del in the body may run before a read in the next pass)
            pre = dict(fl.defd)
            outer = fl.brks
            fl.brks = []
            if k == "for":
                self.fl_target(fl, n.kids[0])
            self.fl_stmts(fl, n.kids[2 if k == "for" else 1].kids)
            brks = fl.brks
            fl.brks = outer
            fl.defd = dict(pre)
            if n.kids[-1].s == "else":
                # (after the loop only what was assigned before it is surely assigned)
                self.fl_stmts(fl, n.kids[-1].kids)
                fl.defd = dict(pre)
            if k == "while" and n.kids[0].kind == "True":
                # while True is left only through break
                fl.defd[" dead"] = True
                for b in brks:
                    fl.join(b)
        elif k == "break":
            fl.brks.append(dict(fl.defd))
            fl.defd[" dead"] = True
        elif k == "continue" or k == "return" or k == "raise":
            for c in n.kids:
                self.fl_expr(fl, c)
            if k == "return":
                fl.exposed()
            fl.defd[" dead"] = True
        elif k == "defaults" or k == "cdefaults":
            for d in self.fl_defaults(n):
                self.fl_expr(fl, d)
            fl.defd[n.s] = True
        elif k == "expr" or k == "assert" or k == "del":
            for c in n.kids:
                self.fl_expr(fl, c)
                if k == "del" and c.kind == "name" and c.s in fl.defd:
                    del fl.defd[c.s]  # unbound from here on
        elif k == "with":
            for it in n.kids[:-1]:
                self.fl_expr(fl, it.kids[0])
                if len(it.kids) == 2:
                    self.fl_target(fl, it.kids[1])
            self.fl_stmts(fl, n.kids[-1].kids)

    def fl_target(self, fl: Flow, t: Node) -> None:
        if t.kind == "name":
            fl.defd[t.s] = True
        elif t.kind == "attr" and fl.me != "" and t.kids[0].kind == "name" and t.kids[0].s == fl.me:
            fl.defd["." + t.s] = True
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
        elif k == "attr" and fl.me != "" and e.kids[0].kind == "name" and e.kids[0].s == fl.me:
            if "." + e.s not in fl.defd and " dead" not in fl.defd:
                fl.unsafe[e.s] = True
        elif k == "listcomp":
            # [elt for target in iter if cond]: iter is read outside, the rest with target bound
            self.fl_expr(fl, e.kids[2])
            saved = dict(fl.defd)
            self.fl_target(fl, e.kids[1])
            for i in range(len(e.kids)):
                if i != 1 and i != 2:
                    self.fl_expr(fl, e.kids[i])
            fl.defd = saved
        elif k == "call":
            c = e.kids[0]
            if c.kind == "attr":
                self.fl_expr(fl, c.kids[0])
            elif c.kind != "name":
                self.fl_expr(fl, c)
            elif (c.s in self.funcs or c.s in self.classes) and c.s in fl.tracked and c.s not in fl.defd and " dead" not in fl.defd:
                c.chk = True
                fl.marks[c.s] = True
            for i in range(1, len(e.kids)):
                self.fl_expr(fl, e.kids[i])
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
        # the special methods Pystachy calls implicitly must have the shape it relies on
        if f.name not in SPECIAL:
            return
        self.line = f.node.line
        spec = SPECIAL[f.name]
        n = int(spec[: spec.find(":")])
        ret = spec[spec.find(":") + 1 :]
        if len(f.params) != n:
            self.err(f"{f.name} must take {n - 1} argument{'s' if n != 2 else ''} besides self")
        if ret != "" and f.ret != ret:
            self.err(f"{f.name} must return {ret}")
        if f.name == "__format__" and f.ptypes[1] != "str":
            self.err("__format__ takes the format spec as a str")

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
            if st.kind == "def" or st.kind == "class":
                self.scan_imports(st.kids[-1].kids if st.kind == "class" else st.kids[2].kids)

    def imported(self, name: str) -> str:
        # what an imported name (possibly dotted) refers to, or ""
        root = name[: name.find(".")] if "." in name else name
        return self.imports[root] + name[len(root) :] if root in self.imports else ""

    def check_import(self, a: Node) -> None:
        mod = a.kids[1].s
        tgt = a.kids[0].s
        if mod not in MODULES:
            self.err(f"module '{mod}' is not supported (available: {', '.join(MODULES.keys())})")
        if tgt == mod or tgt == mod[: mod.find(".")] or (tgt + ".") == mod[: len(tgt) + 1]:
            return
        x = tgt[len(mod) + 1 :]
        if mod == "__future__":
            if x not in FUTURE:
                self.err(f"future feature {x} is not defined")
        elif mod == "typing":
            if x not in TYPING:
                self.err(f"cannot import name '{x}' from 'typing'")
        elif mod == "dataclasses":
            if x != "dataclass":
                self.err(f"dataclasses.{x} is not supported")
        elif mod == "builtins":
            return  # a builtin function, checked where it is called
        elif not self.known_path(tgt):
            self.err(f"cannot import name '{x}' from '{mod}' (not supported by Pystachy)")

    def known_path(self, p: str) -> bool:
        # a module attribute Pystachy implements: a CALLS entry, a modattr() value, a module, or
        # a function builtin() handles itself
        if p in MODULES or p in MODATTRS or p == "sys.exit" or p == "os.fspath" or (p.startswith("errno.") and p[6:] in ERRNO):
            return True
        for k in CALLS:
            if k.startswith(p + "(") or k.startswith(p + "."):
                return True
        return False

    def hidden(self, name: str, v: Val) -> str:
        # a compiler-made global, assigned here
        self.global_var(name, lt(v.t))
        self.emit(f"store {lt(v.t)} {v.v}, ptr {name}")
        return name

    def hoist(self, f: FnInfo) -> None:
        # Python evaluates default values once, when the def statement runs
        for j in range(len(f.params)):
            d = f.defaults[j]
            if f.dglob[j] == "" and not is_const(d):
                t = f.ptypes[j]
                self.line = d.line
                bad = self.default_problem(d, t) if f.mod != "" else ""
                if bad != "":
                    # a function of an imported module: the default is an error only where a call needs it
                    f.dglob[j] = "!" + bad
                    continue
                v = self.expr(d, t)
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
            return  # an imported module's class Pystachy cannot compile: an error only where used
        bound: dict[str, bool] = {}
        init = ci.methods["__init__"]
        for st in ci.node.kids[0].kids:
            self.line = st.line
            if st.kind == "annassign" and len(st.kids) == 3 and st.kids[0].kind == "name":
                fl = st.kids[0].s
                self.no_class_names(st.kids[2], bound, ci.name)
                bound[fl] = True
                t = ci.ftypes[fl]
                if self.is_dc(ci.name) and not is_const(st.kids[2]) and (is_list(t) or is_dict(t) or self.is_dc(t) or self.unhashable(t)):
                    self.err(f"mutable default {t} for dataclass field '{fl}' is not allowed")
                if not is_const(st.kids[2]) and fl not in ci.fglob:
                    ci.fglob[fl] = self.hidden(f"@d.c.{ci.name}.{fl}", self.coerce(self.expr(st.kids[2], t), t))
            elif st.kind == "def":
                f = ci.methods[st.s]
                for d in f.defaults:
                    self.no_class_names(d, bound, ci.name)
                bound[st.s] = True
                if f.name != "__init__" or init.node.kids[0].kind != "noann":
                    self.hoist(f)
        if init.node.kids[0].kind == "noann":
            for j in range(1, len(init.params)):
                init.dglob[j] = ci.fglob.get(init.params[j], "")

    def no_class_names(self, e: Node, bound: dict[str, bool], cls: str) -> None:
        if e.kind == "name" and e.s in bound:
            self.err(f"class attribute '{e.s}' of '{cls}' used in a class-body default is not supported")
        for k in e.kids:
            self.no_class_names(k, bound, cls)

    def unhashable(self, t: str) -> bool:
        # a class that defines __eq__ without __hash__ has __hash__ = None in CPython
        return t in self.classes and "__eq__" in self.classes[t].methods and "__hash__" not in self.classes[t].methods

    def while_(self, n: Node) -> None:
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.place(l1)
        self.cbr(self.cond(n.kids[0]), l2, l3)
        self.place(l2)
        self.loop(n.kids[1].kids, l1, l3)
        self.br(l1)
        self.place(l3)

    def loop(self, body: list[Node], cont: str, brk: str) -> None:
        if body is self.elsekids:
            brk = self.elsebrk  # the loop of a for/while ... else: break skips the else block
        self.loops.append(cont)
        self.loops.append(brk)
        self.wdepth.append(len(self.withs))
        self.branch += 1
        self.stmts(body)
        self.branch -= 1
        self.wdepth.pop()
        self.loops.pop()
        self.loops.pop()

    def close_withs(self, depth: int) -> None:
        # leaving with blocks (break, continue, return): their files close, innermost first
        for i in range(len(self.withs) - 1, depth - 1, -1):
            self.rt("pys_file_close", "void", [f"ptr {self.withs[i]}"])

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
        if name in self.classes:
            self.err(f"'{name}' is not an exception class: only the builtin exceptions can be raised (there is no inheritance)")
        if name in self.ltype or name in self.gtypes or name in self.funcs:
            self.err("exceptions must derive from BaseException: raise needs an exception class or a call of one")
        if name not in EXCEPTIONS:
            self.err(f"name '{name}' is not defined")
        if EXCEPTIONS[name] == "-":
            self.err(f"raising {name} is not supported")
        for a in args:
            if a.kind == "kw":
                self.err(f"{name}() takes no keyword arguments")
        if len(args) > 1 and EXCEPTIONS[name] != "":
            self.err(f"{name}() with more than one argument is not supported")
        return args

    def raise_stmt(self, n: Node) -> None:
        # raise E(args) [from C]: CPython's last traceback line, "E: str(arg)" (KeyError: repr(arg);
        # several arguments: their tuple's repr); SystemExit ends the program like sys.exit
        if len(n.kids) == 0:
            self.raise_("RuntimeError", self.sconst("No active exception to reraise"))
            return
        e = n.kids[0]
        args = self.exc_args(e)
        name = e.kids[0].s if e.kind == "call" else e.s
        vals = [self.expr(a, "") for a in args]
        if len(n.kids) > 1 and n.kids[1].kind != "None":
            for a in self.exc_args(n.kids[1]):
                self.expr(a, "")
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
            self.emit("ret void")
            self.term = True
            self.place(l2)
        if name == "SystemExit":
            self.exit_(vals)
            return
        if name == "SyntaxError" or name == "IndentationError" or name == "TabError":
            # CPython's traceback takes str(e), which is str(msg), then prints "E: " and str(msg or
            # "<no detail available>"), the ": " even before an empty str(msg)
            if len(vals) == 1:
                self.to_str(vals[0])
                l1 = self.label()
                l2 = self.label()
                self.cbr(self.truth(vals[0]), l1, l2)
                self.place(l1)
                line = self.rt("pys_str_add", "ptr", [f"ptr {self.sconst(name + ': ')}", f"ptr {self.to_str(vals[0]).v}"])
                self.rt("pys_raise", "void", [f"ptr {line}", f"ptr {self.sconst('')}"])
                self.emit("unreachable")
                self.term = True
                self.place(l2)
            self.raise_(name, self.sconst("<no detail available>"))
            return
        if len(vals) > 1:
            msg = self.repr(self.tuple_(vals)).v
        elif len(vals) == 1:
            msg = (self.repr(vals[0]) if name == "KeyError" else self.to_str(vals[0])).v
        else:
            msg = self.sconst("")
        self.raise_("OSError" if name == "IOError" or name == "EnvironmentError" else name, msg)

    def exit_(self, vals: list[Val]) -> None:
        # sys.exit(code) and raise SystemExit(code): None is status 0, an int is the status, and
        # anything else is printed to stderr with status 1
        if len(vals) > 1:
            self.rt("pys_exit_msg", "void", [f"ptr {self.repr(self.tuple_(vals)).v}"])
        elif len(vals) == 0 or vals[0].t == "None":
            self.rt("pys_exit", "void", ["i64 0"])
        elif vals[0].t == "int" or vals[0].t == "bool":
            self.rt("pys_exit", "void", [f"i64 {self.as_int(vals[0]).v}"])
        else:
            if vals[0].t in self.classes:
                # an object that is None at run time is status 0 too
                l1 = self.label()
                l2 = self.label()
                self.cbr(self.isnull(vals[0]), l1, l2)
                self.place(l1)
                self.rt("pys_exit", "void", ["i64 0"])
                self.emit("unreachable")
                self.term = True
                self.place(l2)
            self.rt("pys_exit_msg", "void", [f"ptr {self.to_str(vals[0]).v}"])
        self.emit("unreachable")
        self.term = True

    def raise_(self, name: str, msg: str) -> None:
        self.rt("pys_raise", "void", [f"ptr {self.sconst(name)}", f"ptr {msg}"])
        self.emit("unreachable")
        self.term = True

    def stmt(self, n: Node) -> None:
        self.line = n.line
        k = n.kind
        if k == "expr":
            if n.kids[0].kind != "str":
                self.expr(n.kids[0], "")
        elif k == "assign":
            val = n.kids[-1]
            t0 = n.kids[0]
            if len(n.kids) == 2 and t0.kind == "name" and (val.kind == "list" or val.kind == "dict") and len(val.kids) == 0 and (self.target_type(t0) == "" or "?" in self.target_type(t0)):
                self.assign(t0, self.empty(val.kind, t0.s))
            elif len(n.kids) == 2 and t0.kind == "tuple" and (val.kind == "tuple" or val.kind == "list") and len(t0.kids) == len(val.kids):
                vs: list[Val] = []
                for i in range(len(val.kids)):
                    vs.append(self.expr(val.kids[i], self.target_type(t0.kids[i])))
                for i in range(len(vs)):
                    self.assign(t0.kids[i], vs[i])
            else:
                v = self.expr(val, self.target_type(t0))
                for i in range(len(n.kids) - 1):
                    self.assign(n.kids[i], v)
        elif k == "annassign":
            t = self.vtype(n.kids[1])
            if n.kids[0].kind == "name":
                self.declare(n.kids[0].s, t)
            if len(n.kids) == 3:
                self.assign(n.kids[0], self.coerce(self.expr(n.kids[2], t), t))
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
            self.stmts(n.kids[1].kids)
            self.br(l3)
            self.place(l2)
            self.stmts(n.kids[2].kids)
            self.branch -= 1
            self.place(l3)
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
            lb = self.elsebrk
            if k == "for":
                self.for_(n, [])
            else:
                self.while_(n)
            self.elsekids = ek
            self.elsebrk = eb
            self.branch += 1
            self.stmts(n.kids[-1].kids)
            self.branch -= 1
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
                # returns; a return of None before it is a placeholder, decided at the end
                v = self.expr(n.kids[0], "") if len(n.kids) > 0 else Val("null", "None")
                self.close_withs(0)
                if v.t == "None":
                    self.emit("ret <none>")
                else:
                    self.ret = v.t
                    self.curfn.ret = v.t
                    self.emit(f"ret {lt(v.t)} {v.v}")
            elif len(n.kids) == 0 or (self.ret == "None" and n.kids[0].kind == "None"):
                if self.ret != "None" and not (self.curfn.infer and self.ret in self.classes):
                    self.err(f"{short(self.curfn.name)}() returns both {self.ret} and None, and None/Optional is only supported for class types" if self.curfn.infer else f"missing return value of type {self.ret}")
                self.close_withs(0)
                self.emit("ret void" if self.ret == "None" else "ret ptr null")
            elif self.ret == "None":
                # return f() where f returns None
                v = self.expr(n.kids[0], "")
                if v.t != "None" and self.curfn.infer:
                    self.err(f"{short(self.curfn.name)}() returns both None and {v.t}, and None/Optional is only supported for class types")
                if v.t != "None":
                    self.err(f"returning {v.t} from a function declared to return None" if self.retann else "returning a value from a function without a return annotation")
                self.close_withs(0)
                self.emit("ret void")
            else:
                v = self.expr(n.kids[0], self.ret)
                if self.curfn.infer and v.t != self.ret and not (v.t == "None" and self.ret in self.classes):
                    self.err(f"{short(self.curfn.name)}() returns both {self.ret} and {v.t} (each function has one return type)")
                v = self.coerce(v, self.ret)
                self.close_withs(0)
                self.emit(f"ret {lt(self.ret)} {v.v}")
            self.term = True
        elif k == "break" or k == "continue":
            if len(self.loops) == 0:
                self.err(f"'{k}' outside loop")
            self.close_withs(self.wdepth[-1])
            self.br(self.loops[-1] if k == "break" else self.loops[-2])
        elif k == "global":
            for nm in n.kids:
                self.gdecl[nm.s] = True
        elif k == "assert" and self.static(n.kids[0]) == 0:
            # an assertion that cannot hold (assert x is not None, x None): code after it never runs
            self.raise_("AssertionError", self.to_str(self.expr(n.kids[1], "")).v if len(n.kids) > 1 else self.sconst(""))
            self.term = True
        elif k == "assert" and self.static(n.kids[0]) == 1:
            pass
        elif k == "assert":
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.cond(n.kids[0]), l2, l1)
            self.place(l1)
            self.raise_("AssertionError", self.to_str(self.expr(n.kids[1], "")).v if len(n.kids) > 1 else self.sconst(""))
            self.place(l2)
        elif k == "raise":
            self.raise_stmt(n)
        elif k == "del":
            for dt in n.kids:
                if dt.kind == "name":
                    self.del_name(dt)
                    continue
                o = self.expr(dt.kids[0], "") if dt.kind == "index" else Val("", "")
                if is_list(o.t):
                    self.rt("pys_list_del", "void", [f"ptr {o.v}", f"i64 {self.ival(dt.kids[1]).v}"])
                elif is_dict(o.t):
                    kt = targs(o.t)[0]
                    self.rt("pys_dict_pop", "i64", [f"ptr {o.v}", "i64 " + self.to_slot(self.coerce(self.expr(dt.kids[1], kt), kt))])
                else:
                    self.err("only 'del list[i]' and 'del dict[key]' are supported")
        elif k == "with":
            # with open(p) as f: the file closes when the block is left, at its end or through
            # break, continue or return (an error ends the program, and exit flushes every file)
            n0 = len(self.withs)
            for it in n.kids[:-1]:
                v = self.expr(it.kids[0], "")
                if v.t != "file":
                    self.err(f"'with' is supported for files only (with open(...) as f:), not {v.t}")
                if len(it.kids) == 2:
                    self.assign(it.kids[1], v)
                self.withs.append(v.v)
            self.stmts(n.kids[-1].kids)
            if not self.term:
                self.close_withs(n0)
            self.withs = self.withs[:n0]
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
            self.br(self.loops[-1])
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
                self.hoist(self.funcs[n.s])
            else:
                self.hoist_class(self.classes[n.s])
            if n.s in self.gflag:
                self.emit(f"store i1 true, ptr @g.{n.s}.def")
        elif k == "import":
            for a in n.kids:
                self.aliases[a.s] = a.kids[0].s
        elif k == "uimport":
            for x in n.kids:
                if x.kind == "guard":
                    # an optional import of a module whose code raises ImportError: it returns there
                    self.emit(f"store i1 true, ptr @init.{x.s}.guard")
                    self.emit(f"call void @init.{x.s}()")
                    self.emit(f"store i1 false, ptr @init.{x.s}.guard")
                else:
                    self.emit(f"call void @init.{x.s}()")
        elif k == "def" or k == "class":
            self.err("nested functions and classes are not supported")
        elif k == "badimport":
            self.err(n.s)
        elif k in UNSUPPORTED:
            self.err(UNSUPPORTED[k])
        elif k != "pass":
            self.err(f"unsupported statement '{k}'")

    def del_name(self, n: Node) -> None:
        # del x: x is unbound afterwards. Reads that may follow test its "is assigned" flag
        # (definite assignment marks them), so clearing the flag is all it takes.
        name = n.s
        if name in self.unsupported:
            return  # a class of an imported module that is never compiled
        if name in self.funcs or name in self.classes or name in self.aliases:
            self.err(f"del of '{name}' is not supported: only variables can be deleted")
        if not self.modlevel and self.is_global(name):
            self.err(f"del of the global '{name}' in a function is not supported")
        if owner(name) != self.curfn.mod:
            self.err(f"del of module {owner(name)}'s attribute '{short(name)}' is not supported")
        self.read(n)  # del of a name that is not bound raises as its read does
        if name in self.ltype and name in self.lflag:
            self.emit(f"store i1 false, ptr {self.lflag[name]}")
        elif name not in self.ltype and name in self.gflag:
            self.emit(f"store i1 false, ptr @g.{name}.def")

    def augassign(self, n: Node) -> None:
        t = n.kids[0]
        op = n.s
        if t.kind == "name" and op == "+" and is_list(self.qtype(t.s)) and "?" in self.qtype(t.s):
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
        elif t.kind == "attr":
            o = self.expr(t.kids[0], "")
            p = self.field(o, t.s, False)
            cur = self.getfield(o, p, t.s)
            self.setfield(o, p, t.s, self.inplace(op, cur, n.kids[1]))
        elif t.kind == "index":
            o = self.expr(t.kids[0], "")
            if is_list(o.t):
                et = elem(o.t)
                i = self.ival(t.kids[1])
                cur = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"]), et)
                r = self.coerce(self.inplace(op, cur, n.kids[1]), et)
                self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {i.v}", "i64 " + self.to_slot(r)])
            elif is_dict(o.t):
                kv = targs(o.t)
                key = self.to_slot(self.coerce(self.expr(t.kids[1], kv[0]), kv[0]))
                cur = self.from_slot(self.rt("pys_dict_getitem", "i64", [f"ptr {o.v}", f"i64 {key}"]), kv[1])
                r = self.coerce(self.inplace(op, cur, n.kids[1]), kv[1])
                self.rt("pys_dict_set", "void", [f"ptr {o.v}", f"i64 {key}", "i64 " + self.to_slot(r)])
            else:
                self.err(f"'{o.t}' does not support item assignment")
        else:
            self.err("invalid target for augmented assignment")

    def inplace(self, op: str, cur: Val, rhs: Node) -> Val:
        # the new value of cur op= rhs: lists change in place (+= extends, *= repeats), objects
        # use __iadd__ & co when they define them, anything else is cur op rhs
        if is_list(cur.t) and op == "+":
            self.rt("pys_list_extend", "void", [f"ptr {cur.v}", f"ptr {self.coerce(self.expr(rhs, cur.t), cur.t).v}"])
            return cur
        if is_list(cur.t) and op == "*":
            self.rt("pys_list_imul", "void", [f"ptr {cur.v}", f"i64 {self.coerce(self.as_int(self.expr(rhs, 'int')), 'int').v}"])
            return cur
        im = "__i" + DUNDER.get(op, "__?")[2:]
        if cur.t in self.classes and im in self.classes[cur.t].methods:
            b = self.expr(rhs, "")
            self.none_operand(op + "=", cur, b)
            return self.call_fn(self.classes[cur.t].methods[im], [cur, b], [])
        return self.arith(op, cur, self.expr(rhs, cur.t), op + "=")

    def objlen(self, v: Val) -> Val:
        r = self.call_fn(self.classes[v.t].methods["__len__"], [v], [])
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
        m2 = self.sconst(f"unsupported operand type(s) for {op}: 'NoneType' and '{tname(b.t)}'")
        self.raise_("TypeError", self.ins(f"select i1 {self.isnull(b)}, ptr {m1}, ptr {m2}"))
        self.place(lok)

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
                seqs = [self.iterable(self.expr(a, "")) for a in args]
                self.for_seq(tgt, seqs, fn, body, "0", hide)
                for i in range(len(args)):
                    self.close_temp(args[i], seqs[i])
                return
            if fn == "enumerate" and len(args) == 2 and (args[1].kind != "kw" or args[1].s == "start"):
                seq = self.iterable(self.expr(args[0], ""))
                a1 = args[1].kids[0] if args[1].kind == "kw" else args[1]
                self.for_seq(tgt, [seq], fn, body, self.ival(a1).v, hide)
                self.close_temp(args[0], seq)
                return
        if it.kind == "call" and len(it.kids) == 1 and it.kids[0].kind == "attr":
            m = it.kids[0].s
            if m == "items" or m == "keys" or m == "values":
                o = self.expr(it.kids[0].kids[0], "")
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

    def iterable(self, v: Val) -> Val:
        # a tuple is iterated as a list of its items, which must then share one type
        if not is_tuple(v.t) or v.t == "tuple[]":
            return v
        ts = targs(v.t)
        for x in ts:
            if x != ts[0]:
                self.err(f"cannot iterate over {v.t}: its items have different types")
        return self.as_list(v, "iter")

    def ival(self, n: Node) -> Val:
        # an index, slice bound or range() argument: an int, or a bool used as one (as CPython does)
        return self.coerce(self.as_int(self.expr(n, "int")), "int")

    def range_args(self, args: list[Node]) -> list[str]:
        vs: list[str] = []
        for a in args:
            vs.append(self.ival(a).v)
        if len(vs) == 1:
            vs.insert(0, "0")
        if len(vs) == 2:
            vs.append("1")
        if len(vs) != 3:
            self.err("range() takes 1 to 3 arguments")
        return vs

    def for_range(self, tgt: Node, start: str, stop: str, step: str, body: list[Node], hide: list[str]) -> None:
        self.hide(hide)
        if step.startswith("%") or int(step) == 0:
            self.guard(self.ins(f"icmp eq i64 {step}, 0"), "ValueError: range() arg 3 must not be zero")
        ctr = self.alloca("int", "")
        self.emit(f"store i64 {start}, ptr {ctr}")
        lc = self.label()
        lb = self.label()
        ls = self.label()
        le = self.label()
        self.place(lc)
        i = self.ins(f"load i64, ptr {ctr}")
        if not step.startswith("%"):
            c = self.ins(f"icmp {'slt' if int(step) > 0 else 'sgt'} i64 {i}, {stop}")
        else:
            up = self.ins(f"icmp slt i64 {i}, {stop}")
            dn = self.ins(f"icmp sgt i64 {i}, {stop}")
            pos = self.ins(f"icmp sgt i64 {step}, 0")
            c = self.ins(f"select i1 {pos}, i1 {up}, i1 {dn}")
        self.cbr(c, lb, le)
        self.place(lb)
        self.assign(tgt, Val(i, "int"))
        self.loop(body, ls, le)
        self.place(ls)
        # a step that overflows 64 bits has passed any stop value: the loop is over
        r = self.checked("sadd", i, step)
        self.emit(f"store i64 {r[0]}, ptr {ctr}")
        self.cbr(r[1], le, lc)
        self.place(le)

    def for_rrange(self, tgt: Node, vs: list[str], body: list[Node], hide: list[str]) -> None:
        # reversed(range(a, b, s)): the range's items from the last, a + k*s for k = len-1 .. 0
        # (the length is unsigned, and the arithmetic wraps: every result is an item of the range)
        self.hide(hide)
        n = self.rt("pys_range_len", "i64", [f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"])
        ctr = self.alloca("int", "")
        self.emit(f"store i64 {n}, ptr {ctr}")
        lc = self.label()
        lb = self.label()
        ls = self.label()
        le = self.label()
        self.place(lc)
        c = self.ins(f"load i64, ptr {ctr}")
        self.cbr(self.ins(f"icmp ne i64 {c}, 0"), lb, le)
        self.place(lb)
        k = self.ins(f"sub i64 {c}, 1")
        self.emit(f"store i64 {k}, ptr {ctr}")
        self.assign(tgt, Val(self.ins(f"add i64 {vs[0]}, {self.ins(f'mul i64 {k}, {vs[2]}')}"), "int"))
        self.loop(body, ls, le)
        self.place(ls)
        self.br(lc)
        self.place(le)

    def for_seq(self, tgt: Node, seqs: list[Val], mode: str, body: list[Node], start: str, hide: list[str]) -> None:
        self.hide(hide)
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
            if is_dict(s.t):
                self.emit(f"store i64 {nx}, ptr {st[k]}")
            at.append(j)
        vals: list[Val] = []
        if mode == "enumerate":
            vals.append(Val(i if start == "0" else self.iop("sadd", i, start), "int"))
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
        self.loop(body, ls, le)
        self.place(ls)
        nx2 = self.ins(f"add i64 {i}, 1")
        self.emit(f"store i64 {nx2}, ptr {ctr}")
        self.br(lc)
        self.place(le)

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
            r = -1 if t == "" or t in self.classes else 1 if t == "None" else 0
            return r if r < 0 or n.s == "is" else 1 - r
        if k == "call" and n.kids[0].kind == "name" and n.kids[0].s == "hasattr" and not self.bound("hasattr") and len(n.kids) == 3 and n.kids[2].kind == "str":
            t = self.static_type(n.kids[1])
            return max(self.has(t, n.kids[2].s), -1) if t != "" else -1
        if k == "call" and n.kids[0].kind == "name" and n.kids[0].s == "isinstance" and not self.bound("isinstance") and len(n.kids) == 3:
            t = self.static_type(n.kids[1])
            return self.isinst(t, n.kids[2]) if t != "" else -1
        return -1

    def has(self, t: str, a: str) -> int:
        # hasattr(x, a) for x of static type t: 1 or 0; for an object's own attribute -1 (true
        # unless it is None), or -2 for a field __init__ may leave unassigned (its flag says).
        # The builtin types have CPython 3.13's attributes.
        if a in HASATTR["any"].split():
            return 1
        if t == "None":
            return 1 if a == "__bool__" else 0
        if t in self.classes:
            ci = self.classes[t]
            if a in ci.fflag:
                return -2
            if a in ci.methods or a in ci.ftypes or a in HASATTR["obj"].split():
                return -1
            return -1 if self.is_dc(t) and a in "__dataclass_fields__ __dataclass_params__ __match_args__".split() else 0
        b = "list" if is_list(t) else "dict" if is_dict(t) else "tuple" if is_tuple(t) else "int" if t == "bool" else t
        if b in HASATTR:
            return 1 if a in HASATTR[b].split() else 0
        self.err(f"hasattr() of '{a}' on a {tname(t)} is not supported")
        return 0

    def static_type(self, n: Node) -> str:
        # the type of a variable read that cannot fail, or ""
        if n.kind != "name" or n.chk:
            return ""
        if (n.s in self.nonevars or n.s in self.noneglobals) and n.s not in self.ltype:
            return "None"
        if n.s in self.ltype:
            return self.ltype[n.s]
        if self.is_global(n.s) and n.s in self.gtypes and n.s not in self.gflag:
            return self.gtypes[n.s]
        return ""

    def only_class(self, t: str, c: Node) -> bool:
        # isinstance(x, c) for an object x of class t is "x is not None": c names t, alone or with
        # types x cannot have
        if c.kind == "binop" and c.s == "|":
            return self.only_class(t, mk("tuple", "", c.line, c.kids))
        if c.kind == "name":
            return c.s == t
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
        if c.kind == "tuple":
            r = 0
            for x in c.kids:
                y = self.isinst(t, x)
                if y == 1:
                    return 1
                if y < 0:
                    r = -1
            return r
        if c.kind != "name":
            return -1
        if c.s in self.classes:
            return -1 if t == c.s else 0
        if self.bound(c.s):
            return -1
        if c.s == "object":
            return 1
        if c.s == "int":
            return 1 if t == "int" or t == "bool" else 0
        if c.s == "bool" or c.s == "float" or c.s == "str":
            return 1 if t == c.s else 0
        if c.s == "list" or c.s == "dict" or c.s == "tuple":
            return 1 if t.startswith(c.s + "[") else 0
        if c.s in "bytes bytearray memoryview set frozenset complex range slice type".split():
            return 0
        return -1

    # ---- expressions
    def cond(self, n: Node) -> str:
        if n.kind == "name" and "?" in self.qtype(n.s):
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
            return self.ins(f"phi i1 [false, %{e1}], [{r}, %{e2}]")
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
            return Val(self.sconst(n.s), "str")
        if k == "True" or k == "False":
            return Val(k.lower(), "bool")
        if k == "None":
            return Val("null", "None")
        if k == "name":
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
            o = self.expr(n.kids[0], "")
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
                    # a given bound of -2**63 clamps exactly like -2**63 + 1, which is not the marker
                    bd = self.ival(x).v
                    if bd.startswith("%"):
                        bd = self.ins(f"select i1 {self.ins(f'icmp eq i64 {bd}, -9223372036854775808')}, i64 -9223372036854775807, i64 {bd}")
                    elif bd == "-9223372036854775808":
                        bd = "-9223372036854775807"
                    bnd.append(bd)
            if o.t != "str" and not is_list(o.t):
                self.err(f"'{o.t}' cannot be sliced")
            fn = "pys_str_slice" if o.t == "str" else "pys_list_slice"
            return Val(self.rt(fn, "ptr", [f"ptr {o.v}", f"i64 {bnd[0]}", f"i64 {bnd[1]}"]), o.t)
        if k == "list":
            et = elem(want) if is_list(want) and "?" not in want else ""
            items: list[Val] = []
            for e in n.kids:
                v = self.expr(e, et)
                if et == "" and v.t != "None":
                    et = v.t
                items.append(v)
            if et == "" or et == "None":
                self.err(f"cannot infer the type of {'an empty list' if len(items) == 0 else 'a list of None'}; add a type annotation")
            items = [self.coerce(v, et) for v in items]
            r = self.rt("pys_list_new", "ptr", [f"i64 {len(items)}"])
            for v in items:
                self.rt("pys_list_append", "void", [f"ptr {r}", "i64 " + self.to_slot(v)])
            return Val(r, f"list[{et}]")
        if k == "dict":
            kv = targs(want) if is_dict(want) and "?" not in want else ["", ""]
            ks: list[Val] = []
            vs: list[Val] = []
            for i in range(0, len(n.kids), 2):
                a = self.expr(n.kids[i], kv[0])
                if kv[0] == "":
                    kv[0] = a.t
                b = self.expr(n.kids[i + 1], kv[1])
                if kv[1] == "" and b.t != "None":
                    kv[1] = b.t
                ks.append(self.coerce(a, kv[0]))
                vs.append(b)
            if kv[0] == "" or kv[1] == "":
                self.err(f"cannot infer the type of {'an empty dict' if len(ks) == 0 else 'a dict of None values'}; add a type annotation")
            vs = [self.coerce(x, kv[1]) for x in vs]
            if kv[0] != "int" and kv[0] != "str":
                self.err("dict keys must be int or str")
            r = self.rt("pys_dict_new", "ptr", [f"i64 {1 if kv[0] == 'str' else 0}", f"i64 {len(ks)}"])
            for i in range(len(ks)):
                self.rt("pys_dict_set", "void", [f"ptr {r}", "i64 " + self.to_slot(ks[i]), "i64 " + self.to_slot(vs[i])])
            return Val(r, f"dict[{kv[0]},{kv[1]}]")
        if k == "tuple":
            ws = targs(want) if is_tuple(want) else []
            vals: list[Val] = []
            for i in range(len(n.kids)):
                v = self.expr(n.kids[i], ws[i] if i < len(ws) else "")
                if v.t == "None" and i < len(ws) and ws[i] in self.classes:
                    v = self.coerce(v, ws[i])
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

    def percent(self, fmt: str, rhs: Node) -> Val:
        # "format" % args with a constant format: each conversion becomes what format() or
        # str()/repr() of its argument gives, as CPython's printf-style formatting does
        items: list[Val] = []
        if rhs.kind == "tuple":
            for x in rhs.kids:
                items.append(self.expr(x, ""))
        else:
            v = self.expr(rhs, "")
            if is_tuple(v.t):
                for i in range(len(targs(v.t))):
                    items.append(self.tget(v, i))
            elif is_dict(v.t) and "%(" in fmt:
                self.err("% formatting with a mapping (%(name)s) is not supported")
            else:
                items.append(v)
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
            acc = self.cat(acc, self.conversion(v, flags, width, prec, t))
        if used < len(items):
            return self.fmt_error("not all arguments converted during string formatting")
        if len(lit) > 0:
            acc = self.cat(acc, Val(self.sconst("".join(lit)), "str"))
        return acc

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
            if v.t == "str":
                return v
            v = self.coerce(self.as_int(v), "int")
            cv = Val(self.rt("pys_chr", "ptr", [f"i64 {v.v}"]), "str")
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
                self.err(f"%{t} format: a real number is required, not {tname(v.t)}")
            return self.format_(v, mk("str", spec + ("d" if t == "i" or t == "u" else t), self.line, []))
        v = self.as_float(self.as_int(v))
        if v.t != "float":
            self.err(f"must be real number, not {tname(v.t)}")
        return self.format_(v, mk("str", spec + (prec if prec != "" else ".6") + t, self.line, []))

    def format_(self, v: Val, spec: Node) -> Val:
        # format(v, spec), as an f-string field computes it; spec is a str or an f-string node
        empty = spec.kind == "str" and spec.s == ""
        if v.t in self.classes and "__format__" in self.classes[v.t].methods:
            sv = self.expr(spec, "str")
            if v.v not in self.nn:
                # None's own __format__ accepts only an empty spec
                self.guard(self.ins(f"icmp eq ptr {v.v}, null"), "TypeError: unsupported format string passed to NoneType.__format__")
            return self.call_fn(self.classes[v.t].methods["__format__"], [v, sv], [])
        if empty or v.t == "None":
            if not empty and spec.kind == "str":
                self.err("unsupported format string passed to NoneType.__format__")
            return self.to_str(v)
        if v.t in self.classes or v.t == "file":
            if spec.kind == "str":
                self.err(f"unsupported format string passed to {tname(v.t)}.__format__")
            # a computed spec: str(v) when it turns out empty, TypeError otherwise
            sv = self.expr(spec, "str")
            self.guard(self.ins(f"icmp ne i64 {self.ins(f'load i64, ptr {sv.v}')}, 0"), f"TypeError: unsupported format string passed to {tname(v.t)}.__format__")
            return self.to_str(v)
        if spec.kind == "str" and not self.isnum(v.t) and v.t != "str":
            self.err(f"unsupported format string passed to {tname(v.t)}.__format__")
        sv = self.expr(spec, "str")
        d = self.sconst(self.desc(v.t))
        return Val(self.rt("pys_format", "ptr", ["i64 " + self.to_slot(v), f"ptr {d}", f"ptr {sv.v}"]), "str")

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
        t = o.t
        if is_list(t) or t == "str":
            i = self.ival(n.kids[1])
            if t == "str":
                return Val(self.rt("pys_str_get", "ptr", [f"ptr {o.v}", f"i64 {i.v}"]), "str")
            return self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"]), elem(t))
        if is_dict(t):
            kv = targs(t)
            key = self.to_slot(self.coerce(self.expr(n.kids[1], kv[0]), kv[0]))
            return self.from_slot(self.rt("pys_dict_getitem", "i64", [f"ptr {o.v}", f"i64 {key}"]), kv[1])
        if is_tuple(t):
            ts = targs(t)
            i = self.expr(n.kids[1], "int")
            if i.t == "bool" and (i.v == "true" or i.v == "false"):
                i = Val("1" if i.v == "true" else "0", "int")
            if i.t != "int" or i.v.startswith("%"):
                self.err("tuple index must be an integer constant")
            j = int(i.v)
            if j < 0:
                j += len(ts)
            if j < 0 or j >= len(ts):
                self.err("tuple index out of range")
            return self.tget(o, j)
        self.err(f"'{t}' object is not subscriptable")
        return o

    def listcomp(self, n: Node, want: str, mode: str = "") -> Val:
        # [e for t in it if c] runs as a loop appending to a fresh list; t is scoped to it.
        # mode any/all: any(e for ...) / all(...) instead, stopping at the deciding element.
        if mode != "":
            res = self.alloca("bool", "")
            self.emit(f"store i1 {'false' if mode == 'any' else 'true'}, ptr {res}")
        else:
            res = self.rt("pys_list_new", "ptr", ["i64 0"])
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
        self.for_(mk("for", "", n.line, [n.kids[1], n.kids[2], mk("block", "", n.line, body)]), names)
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
        a = self.expr(n.kids[1], want)
        # an arm that ends the program (sys.exit()) has no edge to the join, and no value
        e1 = "" if self.term else self.cur
        self.br(l3)
        self.place(l2)
        b = self.expr(n.kids[2], want if want != "" else a.t)
        e2 = "" if self.term else self.cur
        t = b.t if e1 == "" or (a.t == "None" and e2 != "") else a.t
        phis: list[str] = []
        if e1 != "":
            phis.append(f"[{self.coerce(a, t).v}, %{e1}]")
        if e2 != "":
            phis.append(f"[{self.coerce(b, t).v}, %{e2}]")
        if t == "None":
            self.err("conditional expression has no value")
        self.br(l3)
        self.place(l3)
        return Val(self.ins(f"phi {lt(t)} {', '.join(phis)}"), t)

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
                self.coerce(self.expr(n.kids[1], "None"), "None")
            return Val("null", "None")
        c = self.truth(a)
        if self.term:
            self.place(self.label())
        e1 = self.cur
        l2 = self.label()
        l3 = self.label()
        if n.s == "and":
            self.cbr(c, l2, l3)
        else:
            self.cbr(c, l3, l2)
        self.place(l2)
        b = Val(self.cond(n.kids[1]), "bool") if ascond else self.expr(n.kids[1], a.t)
        # a right operand that ends the program (sys.exit()) has no edge to the join, and no value
        phis = [f"[{a.v}, %{e1}]"]
        if not self.term:
            phis.append(f"[{self.coerce(b, a.t).v}, %{self.cur}]")
        self.br(l3)
        self.place(l3)
        return Val(self.ins(f"phi {lt(a.t)} {', '.join(phis)}"), a.t)

    def unary(self, n: Node) -> Val:
        op = n.s
        e = n.kids[0]
        if op == "not":
            return Val(self.ins(f"xor i1 {self.cond(e)}, true"), "bool")
        if op == "-" and (e.kind == "int" or e.kind == "float"):
            return self.expr(mk(e.kind, "-" + e.s, e.line, []), "")
        v = self.as_int(self.expr(e, ""))
        if v.t == "int" and op == "-":
            return Val(self.iop("ssub", "0", v.v), "int")
        if v.t == "int" and op == "~":
            return Val(self.ins(f"xor i64 {v.v}, -1"), "int")
        if v.t == "float" and op == "-":
            return Val(self.ins(f"fneg double {v.v}"), "float")
        if (v.t == "int" or v.t == "float") and op == "+":
            return v
        self.err(f"bad operand type for unary {op}: {v.t}")
        return v

    def dunder(self, op: str, a: Val, b: Val, shown: str = "") -> Val:
        # operator overloading, resolved statically: a + b -> A.__add__(a, b)
        m = DUNDER.get(op, "")
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

    def cmp_method(self, t: str, m: str, other: str) -> str:
        # m, if class t defines it as a binary method that accepts an operand of type other
        if t not in self.classes or m not in self.classes[t].methods:
            return ""
        f = self.classes[t].methods[m]
        if len(f.params) == 2 and (f.ptypes[1] == other or (other == "None" and f.ptypes[1] in self.classes)):
            return m
        return ""

    def isnull(self, v: Val) -> str:
        # i1: is v None at run time
        if v.t == "None":
            return "true"
        if v.t in self.classes and v.v not in self.nn:
            return self.ins(f"icmp eq ptr {v.v}, null")
        return "false"

    def richcmp(self, op: str, a: Val, b: Val) -> Val:
        # a < b for objects, as CPython does it: a.__lt__(b) if a defines it, else the reflected
        # b.__gt__(a), else TypeError naming both run-time types (None defines neither)
        fw = self.cmp_method(a.t, DUNDER[op], b.t)
        rf = self.cmp_method(b.t, DUNDER[REFL[op]], a.t)
        if fw == "" and rf == "" and not self.lenient:
            self.err(f"'{op}' not supported between instances of '{tname(a.t)}' and '{tname(b.t)}'")
        if fw != "" and a.v in self.nn:
            return self.call_fn(self.classes[a.t].methods[fw], [a, b], [])
        lend = self.label()
        phis: list[str] = []
        if fw != "":
            lcall = self.label()
            lnone = self.label()
            self.cbr(self.isnull(a), lnone, lcall)
            self.place(lcall)
            r = self.call_fn(self.classes[a.t].methods[fw], [a, b], [])
            phis.append(f"[{r.v}, %{self.cur}]")
            self.br(lend)
            self.place(lnone)
        if rf != "":
            lcall = self.label()
            lerr = self.label()
            self.cbr(self.isnull(b), lerr, lcall)
            self.place(lcall)
            r = self.call_fn(self.classes[b.t].methods[rf], [b, a], [])
            phis.append(f"[{r.v}, %{self.cur}]")
            self.br(lend)
            self.place(lerr)
        an = self.isnull(a)
        bn = self.isnull(b)
        ms: list[str] = []
        for x in ["NoneType", tname(a.t)]:
            for y in ["NoneType", tname(b.t)]:
                ms.append(self.sconst(f"'{op}' not supported between instances of '{x}' and '{y}'"))
        mn = self.ins(f"select i1 {bn}, ptr {ms[0]}, ptr {ms[1]}")
        mf = self.ins(f"select i1 {bn}, ptr {ms[2]}, ptr {ms[3]}")
        self.raise_("TypeError", self.ins(f"select i1 {an}, ptr {mn}, ptr {mf}"))
        self.place(lend)
        if len(phis) == 0:
            return Val("false", "bool")
        return Val(self.ins(f"phi i1 {', '.join(phis)}"), "bool")

    def eqcall(self, f: FnInfo, iseq: bool, a: Val, b: Val) -> Val:
        # a == b via __eq__ (or != via __ne__). With None on the left CPython falls back to
        # b's reflected method, or to identity when both are None.
        if a.v in self.nn:
            return self.call_fn(f, [a, b], [])
        same = "true" if iseq else "false"
        lnull = self.label()
        lcall = self.label()
        lend = self.label()
        phis: list[str] = []
        self.cbr(self.ins(f"icmp eq ptr {a.v}, null"), lnull, lcall)
        self.place(lnull)
        if b.t == a.t:
            lboth = self.label()
            lrefl = self.label()
            self.cbr(self.ins(f"icmp eq ptr {b.v}, null"), lboth, lrefl)
            self.place(lboth)
            phis.append(f"[{same}, %{lboth}]")
            self.br(lend)
            self.place(lrefl)
            r = self.call_fn(f, [b, a], [])
            phis.append(f"[{r.v}, %{self.cur}]")
        else:
            # None == None is True; None == <anything else> is False
            phis.append(f"[{same if b.t == 'None' else ('false' if iseq else 'true')}, %{lnull}]")
        self.br(lend)
        self.place(lcall)
        r = self.call_fn(f, [a, b], [])
        phis.append(f"[{r.v}, %{self.cur}]")
        self.br(lend)
        self.place(lend)
        return Val(self.ins(f"phi i1 {', '.join(phis)}"), "bool")

    def arith(self, op: str, a: Val, b: Val, shown: str = "") -> Val:
        du = self.dunder(op, a, b, shown)
        if du.t != "":
            return du
        if a.t == "bool" and b.t == "bool" and (op == "&" or op == "|" or op == "^"):
            return Val(self.ins(f"{IOPS[op]} i1 {a.v}, {b.v}"), "bool")
        a = self.as_int(a)
        b = self.as_int(b)
        if a.t == "int" and b.t == "int" and op == "/":
            return Val(self.rt("pys_idiv", "double", [f"i64 {a.v}", f"i64 {b.v}"]), "float")
        if a.t == "int" and b.t == "int" and op != "/":
            if op in CHECKED:
                return Val(self.iop(CHECKED[op], a.v, b.v), "int")
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
        if op == "*" and seq and b.t == "int":
            return Val(self.rt("pys_str_mul" if a.t == "str" else "pys_list_mul", "ptr", [f"ptr {a.v}", f"i64 {b.v}"]), a.t)
        if op == "*" and a.t == "int" and (b.t == "str" or is_list(b.t)):
            return self.arith(op, b, a)
        self.err(f"unsupported operand types for {op}: {a.t} and {b.t}")
        return a

    def compare(self, n: Node) -> Val:
        ops = n.s.split(",")
        if len(ops) == 1 and (n.kids[0].kind == "list" or n.kids[0].kind == "dict") and len(n.kids[0].kids) == 0:
            # [] == xs, {} in ds: an empty display takes its type from the other side
            b = self.expr(n.kids[1], "")
            w = b.t
            if ops[0] == "in" or ops[0] == "not in":
                w = elem(b.t) if is_list(b.t) else targs(b.t)[0] if is_dict(b.t) else ""
            return self.cmp2(ops[0], self.expr(n.kids[0], w), b)
        a = self.expr(n.kids[0], "")
        if len(ops) == 1 and (ops[0] == "in" or ops[0] == "not in") and self.iterator_call(n.kids[1]) and n.kids[1].kids[0].s == "range":
            # x in range(...): arithmetic, as CPython's range.__contains__ does for ints
            if a.t != "int" and a.t != "bool":
                self.err(f"'in range(...)' needs an int, not {a.t}")
            vs = self.range_args(n.kids[1].kids[1:])
            hit = self.rt("pys_range_has", "i64", [f"i64 {self.as_int(a).v}", f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"])
            return Val(self.ins(f"icmp {'ne' if ops[0] == 'in' else 'eq'} i64 {hit}, 0"), "bool")
        if len(ops) == 1:
            return self.cmp2(ops[0], a, self.expr(n.kids[1], a.t))
        l3 = self.label()
        phis: list[str] = []
        r = a
        for i in range(len(ops)):
            b = self.expr(n.kids[i + 1], a.t)
            r = self.cmp2(ops[i], a, b)
            if i < len(ops) - 1:
                nx = self.label()
                phis.append(f"[false, %{self.cur}]")
                self.cbr(r.v, nx, l3)
                self.place(nx)
            a = b
        phis.append(f"[{r.v}, %{self.cur}]")
        self.br(l3)
        self.place(l3)
        return Val(self.ins(f"phi i1 {', '.join(phis)}"), "bool")

    def cmp2(self, op: str, a: Val, b: Val) -> Val:
        if (op == "==" or op == "!=") and a.t == "file" and b.t == "file":
            # files compare by identity, as CPython's do
            return Val(self.ins(f"icmp {'eq' if op == '==' else 'ne'} ptr {a.v}, {b.v}"), "bool")
        if op == "is" or op == "is not":
            if (a.t == "None") != (b.t == "None") and (not self.isref(a.t) or not self.isref(b.t)):
                # a number or bool is never None
                return Val("false" if op == "is" else "true", "bool")
            if not self.isref(a.t) or not self.isref(b.t):
                self.err("'is' is only supported for objects and None")
            return Val(self.ins(f"icmp {'eq' if op == 'is' else 'ne'} ptr {a.v}, {b.v}"), "bool")
        du = self.dunder(op, a, b)
        if du.t != "":
            return du
        if (op == "in" or op == "not in") and is_tuple(b.t):
            # CPython: for each item in order, item is x or item == x; stop at the first match
            lend = self.label()
            phis: list[str] = []
            for i in range(len(targs(b.t))):
                item = self.tget(b, i)
                if not self.comparable(item.t, a.t):
                    continue
                if item.t in self.classes and self.isref(a.t):
                    nx = self.label()
                    phis.append(f"[true, %{self.cur}]")
                    self.cbr(self.ins(f"icmp eq ptr {item.v}, {a.v}"), lend, nx)
                    self.place(nx)
                c = self.cmp2("==", item, a)
                nx = self.label()
                phis.append(f"[true, %{self.cur}]")
                self.cbr(c.v, lend, nx)
                self.place(nx)
            phis.append(f"[false, %{self.cur}]")
            self.br(lend)
            self.place(lend)
            r = self.ins(f"phi i1 {', '.join(phis)}")
            return Val(r if op == "in" else self.ins(f"xor i1 {r}, true"), "bool")
        if op == "in" or op == "not in":
            r = ""
            if b.t == "str":
                r = self.rt("pys_str_contains", "i64", [f"ptr {b.v}", f"ptr {self.coerce(a, 'str').v}"])
            elif is_list(b.t):
                s = self.to_slot(self.coerce(a, elem(b.t)))
                r = self.rt("pys_list_find", "i64", [f"ptr {b.v}", f"i64 {s}", f"ptr {self.sconst(self.desc(elem(b.t)))}"])
                r = self.ins(f"add i64 {r}, 1")
            elif is_dict(b.t):
                s = self.to_slot(self.coerce(a, targs(b.t)[0]))
                r = self.rt("pys_dict_has", "i64", [f"ptr {b.v}", f"i64 {s}"])
            else:
                self.err(f"'in' is not supported for {b.t}")
            return Val(self.ins(f"icmp {'ne' if op == 'in' else 'eq'} i64 {r}, 0"), "bool")
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
                r = self.ins(f"select i1 {self.ins(f'icmp eq i64 {r}, 2')}, i64 2, i64 {self.ins(f'sub i64 0, {r}')}")
            return Val(self.ins(MIXCMP[op].replace("R", r)), "bool")
        eq = op == "==" or op == "!="
        if eq and (a.t == "None" or b.t == "None" or (a.t == b.t and a.t in self.classes)) and self.isref(a.t) and self.isref(b.t):
            return Val(self.ins(f"icmp {ICMP[op]} ptr {a.v}, {b.v}"), "bool")
        if a.t == b.t and (a.t == "str" or is_list(a.t) or is_tuple(a.t) or (eq and is_dict(a.t))):
            d = f"ptr {self.sconst(self.desc(a.t))}"
            sa = self.to_slot(a)
            sb = self.to_slot(b)
            if eq:
                r = self.rt("pys_eq", "i64", [f"i64 {sa}", f"i64 {sb}", d])
                return Val(self.ins(f"icmp {'ne' if op == '==' else 'eq'} i64 {r}, 0"), "bool")
            r = self.rt("pys_cmpop", "i64", [f"i64 {sa}", f"i64 {sb}", d, f"i64 {ORDOP[op]}"])
            return Val(self.ins(f"icmp ne i64 {r}, 0"), "bool")
        self.err(f"cannot compare {a.t} {op} {b.t}")
        return a

    def comparable(self, t: str, u: str) -> bool:
        # can t == u be true at all? (otherwise CPython just answers False)
        if t == u or (self.isnum(t) and self.isnum(u)):
            return True
        return (t == "None" and u in self.classes) or (u == "None" and t in self.classes)

    # ---- calls
    def call(self, n: Node, want: str) -> Val:
        f = n.kids[0]
        args = n.kids[1:]
        if f.kind == "badattr":
            self.err(f.s)
        for a in args:
            if a.kind == "starred" or a.kind == "dstar":
                self.err("star arguments are not supported")
        if f.kind == "name" and f.s not in self.ltype:
            if (f.chk or self.foreign(f.s)) and f.s in self.gflag:
                # a call that may run before the def or class statement
                bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{f.s}.def')}, true")
                self.guard(bad, self.unbound(f.s))
            if f.s in self.funcs:
                return self.call_fn(self.funcs[f.s], [], args)
            if f.s in self.aliases and f.s not in self.gtypes:
                return self.builtin(self.aliases[f.s], args, want)
            if f.s in self.classes:
                if self.classes[f.s].bad != "":
                    self.err(self.classes[f.s].bad)
                size = f"ptrtoint (ptr getelementptr (%C.{f.s}, ptr null, i32 1) to i64)"
                o = Val(self.rt("pys_alloc", "ptr", [f"i64 {size}"]), f.s)
                self.nn[o.v] = True
                self.call_fn(self.classes[f.s].methods["__init__"], [o], args)
                return o
            if f.s in self.mvars:
                self.err(f"'{f.s}' is a variable, so it cannot be called")
            if f.s in self.unsupported:
                self.err(self.unsupported[f.s])
            return self.builtin(f.s, args, want)
        if f.kind == "attr":
            path = self.dotted(f)
            if path != "" and path[: path.rfind(".")] not in MODATTRS:
                return self.builtin(path, args, want)
            if f.kids[0].kind == "name" and "?" in self.qtype(f.kids[0].s):
                return self.fill(f.kids[0], f.s, args)
            o = self.expr(f.kids[0], "")
            r = self.method(o, f.s, args)
            if f.s != "close":
                self.close_temp(f.kids[0], o)
            return r
        self.err("only functions, classes and methods can be called")
        return Val("", "")

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
            vals[nm] = self.coerce(v, want).v
        return Val(self.rt("pys_open", "ptr", [f"ptr {vals['file']}", f"ptr {vals['mode']}", f"ptr {vals['encoding']}", f"ptr {vals['newline']}",
                                               f"i64 {vals['buffering']}"]), "file")

    def method(self, o: Val, m: str, args: list[Node]) -> Val:
        if o.t in self.classes:
            ci = self.classes[o.t]
            if m not in ci.methods:
                self.err(f"'{o.t}' object has no method '{m}'")
            self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{m}'")
            return self.call_fn(ci.methods[m], [o], args)
        return self.bmethod(o, m, args)

    def pcoerce(self, v: Val, t: str) -> Val:
        # an argument for a parameter of type t ("": a template's unannotated parameter takes any type)
        return v if t == "" else self.coerce(v, t)

    def call_fn(self, f: FnInfo, pre: list[Val], args: list[Node]) -> Val:
        if f.bad != "" and not f.generic:
            self.err(f.bad)
        self.called[f.ll] = True
        line = self.line
        np = len(f.params)
        vals: list[Val] = []
        for i in range(np):
            vals.append(self.pcoerce(pre[i], f.ptypes[i]) if i < len(pre) else Val("", ""))
        pos = len(pre)
        extra: list[Val] = []
        for a in args:
            j = pos
            e = a
            if a.kind == "starred" or a.kind == "dstar":
                self.err("star arguments are not supported")
            if a.kind != "kw" and f.vararg >= 0 and j >= f.vararg:
                extra.append(self.pcoerce(self.expr(a, f.varelem), f.varelem))
                pos += 1
                continue
            if a.kind == "kw" and f.vararg >= 0 and a.s == f.params[f.vararg]:
                self.err(f"{f.name}() got an unexpected keyword argument '{a.s}'")
            if a.kind == "kw":
                if a.s not in f.params:
                    self.err(f"{f.name}() got an unexpected keyword argument '{a.s}'")
                j = f.params.index(a.s)
                if j < f.posonly:
                    self.err(f"{f.name}() got a positional-only argument passed as a keyword argument: '{a.s}'")
                e = a.kids[0]
            else:
                pos += 1
                if j >= f.npos and f.npos >= 0 and j < np:
                    self.err(f"{f.name}() takes {f.npos} positional argument{'s' if f.npos != 1 else ''} but more were given")
            if j >= np:
                self.err(f"too many arguments in call to {f.name}()")
            if vals[j].t != "":
                self.err(f"{f.name}() got multiple values for argument '{f.params[j]}'")
            vals[j] = self.pcoerce(self.expr(e, f.ptypes[j]), f.ptypes[j])
        if f.vararg >= 0:
            vals[f.vararg] = self.tuple_(extra)
        for j in range(np):
            if vals[j].t == "":
                if f.defaults[j].kind == "noann":
                    self.err(f"missing argument '{f.params[j]}' in call to {f.name}()")
                t = f.ptypes[j]
                if f.dglob[j].startswith("!"):
                    self.err(f.dglob[j][1:])
                if f.dglob[j] == "=None":
                    vals[j] = Val("null", "None")
                elif f.dglob[j] != "":
                    t = t if t != "" else f.dtypes[j]
                    vals[j] = Val(self.ins(f"load {lt(t)}, ptr {f.dglob[j]}"), t)
                else:
                    vals[j] = self.pcoerce(self.expr(f.defaults[j], t), t)
        self.line = line
        if f.generic:
            f = self.instance(f, [v.t for v in vals])
        call = f"call {lt(f.ret)} {f.ll}({', '.join([lt(v.t) + ' ' + v.v for v in vals if v.t != 'None'])})"
        if f.ret == "None":
            self.emit(call)
            return Val("null", "None")
        return Val(self.ins(call), f.ret)

    def instance(self, f: FnInfo, ts: list[str]) -> FnInfo:
        # the function template f compiles to for arguments of types ts, compiled when first
        # needed, in the middle of the function that calls it: its first return statement
        # decides what it returns
        key = ",".join(ts)
        if key in f.insts:
            g = f.insts[key]
            if g.ret == "":
                self.err(f"cannot infer what {short(f.name)}() returns: it calls itself before a return statement does; annotate its return type")
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
        f.insts[key] = g
        self.making.append(f"compiling {shown(f.name)}({', '.join(ts)}) for the call at {where(self.line)}")
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
            if n.s in self.aliases and n.s not in self.ltype and n.s not in self.gtypes and n.s not in self.compvars:
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
        if name == "__pys_repr_enter" or name == "__pys_repr_leave":
            o = self.expr(args[0], "")
            r = self.rt(name[2:], "i64" if name.endswith("enter") else "void", [f"ptr {o.v}"])
            return Val(self.ins(f"icmp ne i64 {r}, 0"), "bool") if name.endswith("enter") else Val("null", "None")
        if name == "__pys_repr" or name == "__pys_str" or name == "__pys_ascii":
            # compiler-written calls (f"{x!r}", dataclass __repr__): always the builtin
            name = name[6:]
        if name.startswith("builtins."):
            name = name[9:]
        if "." not in name and name not in PYBUILTINS:
            self.err(f"name '{short(name)}' is not defined")
        # builtins and module functions ("os.system"); most are one call listed in CALLS
        if name == "print":
            return self.print_(args)
        if name == "open":
            return self.open_(args)
        if name == "map" or name == "filter":
            self.err(f"{name}() is not supported; use a list comprehension")
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
                fv = self.ins(f"load i1, ptr {self.ins(f'getelementptr %C.{hv.t}, ptr {hv.v}, i32 0, i32 {self.classes[hv.t].fflag[args[1].s]}')}")
                e1 = self.cur
                self.br(l2)
                self.place(l2)
                return Val(self.ins(f"phi i1 [false, %{e0}], [{fv}, %{e1}]"), "bool")
            if hy < 0:
                return Val(self.ins(f"icmp ne ptr {hv.v}, null"), "bool")
            return Val("true" if hy == 1 else "false", "bool")
        if name == "isinstance" and len(args) == 2 and args[0].kind != "kw" and args[1].kind != "kw":
            # decided by the static types, or for an object by whether it is None
            v = self.expr(args[0], "")
            known = self.isinst(v.t, args[1])
            if known < 0 and v.t in self.classes and self.only_class(v.t, args[1]):
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
                self.err(f"{name}() does not accept keyword arguments")
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
        elif (name == "len" or name == "bool") and len(args) == 1 and args[0].kind == "name" and "?" in self.qtype(args[0].s):
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
            self.exit_(vals)
            return Val("null", "None")
        if name == "os.fspath" and len(vals) == 1 and vals[0].t == "str":
            return vals[0]  # a str path is its own file system path
        if name == "os.getenv" and len(vals) == 1:
            self.err("os.getenv(name) needs a default here, os.getenv(name, default): the result would be str or None")
        if (name == "math.floor" or name == "math.ceil" or name == "math.trunc") and len(vals) == 1 and (vals[0].t == "int" or vals[0].t == "bool"):
            return self.as_int(vals[0])
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
            neg = self.iop("ssub", "0", v.v)
            return Val(self.ins(f"select i1 {c}, i64 {neg}, i64 {v.v}"), "int")
        elif (name == "min" or name == "max") and len(vals) == 1 and is_list(t):
            d = self.sconst(self.desc(elem(t)))
            r = self.rt("pys_list_minmax", "i64", [f"ptr {v.v}", f"ptr {d}", f"i64 {1 if name == 'max' else 0}"])
            return self.from_slot(r, elem(t))
        elif (name == "min" or name == "max") and len(vals) == 1:
            self.err(f"'{tname(t)}' object is not iterable")
        elif name == "min" or name == "max":
            for b in vals[1:]:
                b = self.coerce(b, t)
                gt = self.cmp2(">" if name == "max" else "<", b, v)
                v = Val(self.ins(f"select i1 {gt.v}, {lt(t)} {b.v}, {lt(t)} {v.v}"), t)
            return v
        elif (name == "sorted" or name == "list") and is_list(t):
            c = v.v if fresh else self.rt("pys_list_copy", "ptr", [f"ptr {v.v}"])
            if name == "sorted":
                self.rt("pys_list_sort_r", "void", [f"ptr {c}", f"ptr {self.sconst(self.desc(elem(t)))}", f"i64 {rev}"])
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
        self.place(lc)
        i = self.ins(f"load i64, ptr {ctr}")
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
        # sorted(d), max(t), ...: a dict's keys, or the items of a tuple of one item type, as a list
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
                    sv = self.coerce(self.expr(x, "str"), "str").v
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
            self.rt("pys_list_sort_r", "void", [f"ptr {o.v}", f"ptr {self.sconst(self.desc(elem(o.t)))}", f"i64 {rev}"])
            return Val("null", "None")
        for a in args:
            if a.kind == "kw":
                self.err(f"keyword arguments to {tname(o.t)}.{m}() are not supported; pass them by position")
        if is_dict(o.t) and m == "pop" and len(args) == 2:
            kv = targs(o.t)
            k = self.to_slot(self.coerce(self.expr(args[0], kv[0]), kv[0]))
            dv = self.to_slot(self.coerce(self.expr(args[1], kv[1]), kv[1]))
            return self.from_slot(self.rt("pys_dict_pop_default", "i64", [f"ptr {o.v}", f"i64 {k}", f"i64 {dv}"]), kv[1])
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
        if key not in METHODS:
            self.err(f"'{o.t}' has no method '{m}'")
        if key == "dict.get" and len(args) == 1 and V not in self.classes:
            self.err("dict.get(key) needs a default value unless the values are objects")
        spec = METHODS[key]
        c = spec.find(":")
        av = [f"{lt(o.t)} {o.v}"]
        i = 0
        for p in spec[c + 1 :].split(","):
            if p == "":
                continue
            if p == "#":
                av.append(f"ptr {self.sconst(self.desc(T))}")
                continue
            dflt = ""
            e = p.find("=")
            if e >= 0:
                dflt = p[e + 1 :]
                p = p[:e]
            slot = p.startswith("*")
            pt = subst(p[1:] if slot else p, T, K, V, o.t)
            if i < len(args) and dflt == "null" and args[i].kind == "None":
                av.append(rtt(pt) + " null")  # an explicit None: the default
            elif i < len(args):
                v = self.consume(args[i], pt) if key == "str.join" or key == "list.extend" else self.expr(args[i], pt)
                if key == "str.join":
                    v = self.as_list(v, "join")
                if p == "int":
                    v = self.as_int(v)  # an index or a count may be a bool, as in CPython
                v = self.coerce(v, pt)
                av.append("i64 " + self.to_slot(v) if slot else self.rarg(v))
            elif dflt != "":
                av.append(("i64 " if slot else rtt(pt) + " ") + dflt)
            else:
                self.err(f"missing argument for {m}()")
            i += 1
        if i < len(args):
            self.err(f"too many arguments for {m}()")
        r = spec[:c]
        slot = r.startswith("*")
        rtype = subst(r[1:] if slot else r, T, K, V, o.t)
        res = self.rt(f"pys_{base}_{m}", "i64" if slot else rtt(rtype), av)
        if slot:
            return self.from_slot(res, rtype)
        return self.rres(res, rtype)

    def to_str(self, v: Val) -> Val:
        t = v.t
        if t == "str":
            return v
        if t == "int":
            return Val(self.rt("pys_str_int", "ptr", [f"i64 {v.v}"]), "str")
        if t == "float":
            return Val(self.rt("pys_str_float", "ptr", [f"double {v.v}"]), "str")
        if t == "bool":
            return Val(self.ins(f"select i1 {v.v}, ptr {self.sconst('True')}, ptr {self.sconst('False')}"), "str")
        if t == "None":
            return Val(self.sconst("None"), "str")
        if t in self.classes:
            return self.obj_str(v, "__str__")
        return self.repr(v)

    def obj_str(self, v: Val, m: str) -> Val:
        # str()/repr() of an object through __str__/__repr__; None prints as "None"
        ms = self.classes[v.t].methods
        if m not in ms:
            m = "__repr__"
        if v.v in self.nn and m in ms:
            return self.call_fn(ms[m], [v], [])
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(self.ins(f"icmp eq ptr {v.v}, null"), l1, l2)
        self.place(l1)
        self.br(l3)
        self.place(l2)
        if m in ms:
            r = self.call_fn(ms[m], [v], [])
        else:
            # object.__repr__: <__main__.Name object at 0x...>, <module.Name object at 0x...>
            qn = shown(v.t) if "$" in v.t and not v.t.startswith("__main__$") else "__main__." + short(v.t)
            r = Val(self.rt("pys_default_repr", "ptr", [f"ptr {self.sconst(qn)}", f"ptr {v.v}"]), "str")
        e2 = self.cur
        self.br(l3)
        self.place(l3)
        return Val(self.ins(f"phi ptr [{self.sconst('None')}, %{l1}], [{r.v}, %{e2}]"), "str")

    def repr(self, v: Val) -> Val:
        if v.t in self.classes:
            return self.obj_str(v, "__repr__")
        if v.t == "None":
            return Val(self.sconst("None"), "str")
        if v.t == "file":
            self.err(f"cannot convert {v.t} to str")
        return Val(self.rt("pys_repr", "ptr", ["i64 " + self.to_slot(v), f"ptr {self.sconst(self.desc(v.t))}"]), "str")


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
    argv = sys.argv
    if len(argv) < 3 or (argv[1] != "run" and argv[1] != "build" and argv[1] != "ir"):
        print("usage: pystachy run FILE.py [ARGS...]   JIT-compile and run (LLVM ORC via lli)", file=sys.stderr)
        print("       pystachy build FILE.py [-o EXE]  compile ahead of time to a native executable", file=sys.stderr)
        print("       pystachy ir FILE.py [-o OUT.ll]  emit LLVM IR", file=sys.stderr)
        sys.exit(2)
    cmd = argv[1]
    SRC = argv[2]
    if not os.path.exists(SRC):
        fail("file not found", 0)
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
    # PYSTACHY_CFLAGS: extra clang flags (e.g. -fsanitize=undefined) for the runtime and the AOT link;
    # each flag set caches its own runtime bitcode, named by a 32-bit FNV-1a hash of the flags
    flags = os.getenv("PYSTACHY_CFLAGS", "").split()
    key = 2166136261
    for c in " ".join(flags):
        key = ((key ^ ord(c)) * 16777619) & 0xFFFFFFFF
    rtb = home + ("/build/runtime.bc" if len(flags) == 0 else f"/build/runtime-{key:08x}.bc")
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
    code = sh(f"mkdir -p {q(home + '/build')} && (test {q(rtb)} -nt {q(rtc)} || ({llvm}clang -O2 -S -emit-llvm {q(rtc)} -o {q(rll)}{cflags} && {strip} {q(rll)} | {llvm}llvm-as -o {q(part)} && mv -f {q(part)} {q(rtb)}))")
    if code == 0 and cmd == "run":
        code = sh(f"test {q(rto)} -nt {q(rtc)} || ({llvm}clang -O2 -fPIC -c {q(rtc)} -o {q(part)}{cflags} && mv -f {q(part)} {q(rto)})")
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
        code = sh(f"{fast} {q(ll)} -o {q(bc)} && PYSTACHY_ARGV0={q(SRC)} {llvm}lli -extra-object={q(rto)} {q(bc)} {' '.join([q(a) for a in rest])}")
    for p in [ll, bc, obj, rll, part]:
        if os.path.exists(p):
            os.remove(p)
    os.rmdir(tmp)
    if msg != "":
        fail(msg, 0)
    sys.exit(code)


if __name__ == "__main__":
    main()
