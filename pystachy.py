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


def fail(msg: str, line: int) -> None:
    print(f"{SRC}:{line}: error: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- lexer
KEYWORDS: dict[str, bool] = {}
for _k in "False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield".split():
    KEYWORDS[_k] = True
OPS: list[str] = "**= //= >>= <<= -> ** // == != <= >= += -= *= /= %= &= |= ^= << >> := + - * / % < > = ( ) [ ] { } , : . ; & | ^ ~ @".split()
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
                while self.i < n and src[self.i] == " ":
                    col += 1
                    self.i += 1
                if self.i >= n:
                    break
                c = src[self.i]
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
            elif c == " " or c == "\t" or c == "\r":
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
                fail("integer literal does not fit in 64 bits", self.line)
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
        self.add(w if w in KEYWORDS else "id", w)

    def string(self, prefix: str) -> None:
        src = self.src
        q = src[self.i]
        line = self.line
        triple = src.startswith(q + q + q, self.i)
        self.i += 3 if triple else 1
        start = self.i
        depth = 0  # f-strings: inside a replacement field
        while True:
            if self.i >= len(src):
                fail("unterminated string", line)
            c = src[self.i]
            if c == q and (not triple or src.startswith(q + q + q, self.i)):
                if depth > 0 and not triple:
                    fail("f-string: reusing the string's quote inside a replacement field (PEP 701) is not supported; use the other quote", line)
                break
            if "f" in prefix and (c == "{" or c == "}"):
                if depth == 0 and src[self.i + 1 : self.i + 2] == c:
                    self.i += 2
                    continue
                depth = depth + 1 if c == "{" else max(depth - 1, 0)
            elif "f" in prefix and depth > 0 and (c == "'" or c == '"'):
                # a string inside a field ends at its own quote
                j = src.find(c, self.i + 1)
                if j > 0 and src.find("\n", self.i, j) < 0:
                    self.i = j + 1
                    continue
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
        else:
            self.toks.append(Tok("str", text if "r" in prefix else unescape(text, line), line))

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


def as_target(n: Node) -> Node:
    # [a, b] = ... and for [a, b] in ...: a list display as a target unpacks like a tuple
    if n.kind == "list" or n.kind == "tuple":
        n.kind = "tuple"
        for k in n.kids:
            as_target(k)
    return n


STARTS: dict[str, bool] = {}
for _k in "id int float str fstr rfstr ( [ { - + ~ not None True False lambda".split():
    STARTS[_k] = True
CMPOPS: dict[str, bool] = {"<": True, ">": True, "==": True, ">=": True, "<=": True, "!=": True, "in": True}
AUGOPS: dict[str, bool] = {}
for _k in "+= -= *= /= //= %= **= &= |= ^= <<= >>=".split():
    AUGOPS[_k] = True
BINOPS: list[list[str]] = [["|"], ["^"], ["&"], ["<<", ">>"], ["+", "-"], ["*", "/", "//", "%", "@"]]


class Parser:
    def __init__(self, toks: list[Tok]):
        self.toks = toks
        self.p = 0

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
        if k == "def":
            out.append(self.funcdef())
        elif k == "class":
            self.p += 1
            name = self.expect("id").text
            if self.eat("("):
                if not self.eat(")"):
                    fail("class inheritance is not supported", line)
            self.expect(":")
            out.append(mk("class", name, line, [self.block()]))
        elif k == "if":
            out.append(self.ifstmt())
        elif k == "while":
            self.p += 1
            c = self.test()
            self.expect(":")
            out.append(mk("while", "", line, [c, self.block()]))
        elif k == "for":
            self.p += 1
            t = self.targets()
            self.expect("in")
            it = self.exprlist()
            self.expect(":")
            out.append(mk("for", "", line, [t, it, self.block()]))
        elif k == "@":
            self.p += 1
            name = self.dotted_name()
            self.expect("nl")
            self.stmt(out)
            d = out[-1]
            if d.kind != "class":
                fail(f"unsupported decorator @{name}", line)
            d.kids.append(mk("deco", name, line, []))
        elif k == "with":
            # with open(p) as f, ...: kids are the items (expression [, target]) and the block
            self.p += 1
            items: list[Node] = []
            while True:
                it = mk("withitem", "", line, [self.test()])
                if self.eat("as"):
                    it.kids.append(as_target(self.postfix()))
                items.append(it)
                if not self.eat(","):
                    break
            self.expect(":")
            items.append(self.block())
            out.append(mk("with", "", line, items))
        elif k == "try" or k == "async":
            fail(f"'{k}' statements are not supported", line)
        else:
            self.simple(out)
        if self.peek() == "else" and (k == "for" or k == "while"):
            fail(f"'{k} ... else' is not supported", line)

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
        self.expect("(")
        params = mk("params", "", line, [])
        seen: dict[str, bool] = {}
        while not self.eat(")"):
            if self.peek() == "*" or self.peek() == "**" or self.peek() == "/":
                fail("*args, **kwargs and positional-only markers are not supported", line)
            pname = self.expect("id").text
            if pname in seen:
                fail(f"duplicate argument '{pname}' in function definition", line)
            seen[pname] = True
            ann = mk("noann", "", line, [])
            dflt = mk("noann", "", line, [])
            if self.eat(":"):
                ann = self.test()
            if self.eat("="):
                dflt = self.test()
            elif len(params.kids) > 0 and params.kids[-1].kids[1].kind != "noann":
                fail("parameter without a default follows parameter with a default", line)
            params.kids.append(mk("param", pname, line, [ann, dflt]))
            if not self.eat(","):
                self.expect(")")
                break
        ret = mk("noann", "", line, [])
        if self.eat("->"):
            ret = self.test()
        self.expect(":")
        return mk("def", name, line, [params, ret, self.block()])

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
        if k == "pass" or k == "break" or k == "continue":
            self.p += 1
            return mk(k, "", line, [])
        if k == "return":
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
            if self.peek() == "nl":
                return mk("raise", "", line, [])
            n = mk("raise", "", line, [self.test()])
            if self.peek() == "from":
                self.p += 1
                n.kids.append(self.test())
            return n
        if k == "del":
            self.p += 1
            return mk("del", "", line, [self.test()])
        if k == "nonlocal" or k == "yield":
            fail(f"'{k}' is not supported", line)
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
        # one alias per bound name: s = the name, kids = [target path, imported module]
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
        if self.peek() == ".":
            fail("relative imports are not supported", line)
        path = self.dotted_name()
        self.expect("import")
        paren = self.eat("(")
        while True:
            if self.peek() == "*":
                fail(f"'from {path} import *' is not supported", line)
            x = self.expect("id").text
            name = x
            if self.eat("as"):
                name = self.expect("id").text
            n.kids.append(mk("alias", name, line, [mk("str", path + "." + x, line, []), mk("str", path, line, [])]))
            if not self.eat(",") or (paren and self.peek() == ")"):
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
            fail("starred expressions (*x) are not supported", self.line())
        return self.test()

    def targets(self) -> Node:
        line = self.line()
        e = self.postfix()
        if self.peek() != ",":
            return as_target(e)
        t = mk("tuple", "", line, [e])
        while self.eat(","):
            if self.peek() == "in":
                break
            t.kids.append(self.postfix())
        return as_target(t)

    def test(self) -> Node:
        line = self.line()
        if self.peek() == "lambda":
            fail("lambda is not supported", line)
        e = self.or_test()
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
                        fail("star arguments are not supported", line)
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
                        if self.peek() == "for":
                            a = self.comp(a, line)
                            a.s = "gen"
                            gen = True
                        c.kids.append(a)
                    if not self.eat(","):
                        self.expect(")")
                        break
                if gen and len(c.kids) > 2:
                    fail("Generator expression must be parenthesized", line)
                e = c
            elif self.eat("["):
                lo = mk("omit", "", line, [])
                if self.peek() != ":":
                    lo = self.test()
                if self.eat(":"):
                    hi = mk("omit", "", line, [])
                    if self.peek() != "]" and self.peek() != ":":
                        hi = self.test()
                    if self.peek() == ":":
                        fail("slice steps are not supported", line)
                    self.expect("]")
                    e = mk("slice", "", line, [e, lo, hi])
                else:
                    if self.peek() == ",":
                        t = mk("tuple", "", line, [lo])
                        while self.eat(","):
                            t.kids.append(self.test())
                        lo = t
                    self.expect("]")
                    e = mk("index", "", line, [e, lo])
            elif self.eat("."):
                e = mk("attr", self.expect("id").text, line, [e])
            else:
                return e

    def comp(self, e: Node, line: int) -> Node:
        self.expect("for")
        t = self.targets()
        self.expect("in")
        n = mk("listcomp", "", line, [e, t, self.or_test()])
        if self.eat("if"):
            n.kids.append(self.or_test())
        if self.peek() == "for" or self.peek() == "if":
            fail("nested comprehensions are not supported", line)
        return n

    def atom(self) -> Node:
        t = self.toks[self.p]
        self.p += 1
        k = t.kind
        line = t.line
        if k == "id":
            return mk("name", t.text, line, [])
        if k == "int" or k == "float":
            return mk(k, t.text, line, [])
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
            e = self.test()
            if self.peek() == "for":
                e = self.comp(e, line)
                e.s = "gen"
            elif self.peek() == ",":
                e = mk("tuple", "", line, [e])
                while self.eat(","):
                    if self.peek() == ")":
                        break
                    e.kids.append(self.test())
            self.expect(")")
            return e
        if k == "[":
            items: list[Node] = []
            if self.peek() != "]":
                e = self.test()
                if self.peek() == "for":
                    e = self.comp(e, line)
                    self.expect("]")
                    return e
                items.append(e)
                while self.eat(","):
                    if self.peek() == "]":
                        break
                    items.append(self.test())
            self.expect("]")
            return mk("list", "", line, items)
        if k == "{":
            d = mk("dict", "", line, [])
            while not self.eat("}"):
                d.kids.append(self.test())
                if self.peek() != ":":
                    fail("set literals are not supported", line)
                self.p += 1
                d.kids.append(self.test())
                if self.peek() == "for":
                    fail("dict comprehensions are not supported", line)
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
                        j = s.find(s[j], j + 1)
                        if j < 0:
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
                sub = Parser(Lexer(src.strip(), line).run())
                e = sub.test()
                if sub.peek() != "nl" and sub.peek() != "eof":
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
    "os.getpid()": "pys_getpid:int", "os.path.exists(str)": "pys_exists:bool", "os.getenv(str,str)": "pys_getenv:str",
    "os.remove(str)": "pys_remove:None", "os.rmdir(str)": "pys_rmdir:None", "tempfile.mkdtemp()": "pys_mkdtemp:str",
    "math.floor(float)": "pys_floor:int", "math.ceil(float)": "pys_ceil:int", "math.trunc(float)": "pys_m_trunc:int",
    "math.gcd(int,int)": "pys_m_gcd:int", "math.lcm(int,int)": "pys_m_lcm:int", "math.isqrt(int)": "pys_m_isqrt:int",
    "math.factorial(int)": "pys_m_factorial:int", "math.comb(int,int)": "pys_m_comb:int", "math.perm(int,int)": "pys_m_perm:int",
    "math.isfinite(float)": "pys_m_isfinite:bool", "math.isinf(float)": "pys_m_isinf:bool", "math.isnan(float)": "pys_m_isnan:bool",
    "math.log(float,float)": "pys_m_logb:float",
}
# math functions raise CPython's domain and range errors (runtime.c, pys_m_*)
for _k in "sqrt sin cos tan asin acos atan sinh cosh tanh exp log log2 log10 fabs log1p expm1 exp2 cbrt degrees radians".split():
    CALLS[f"math.{_k}(float)"] = f"pys_m_{_k}:float"
for _k in "pow atan2 hypot fmod copysign".split():
    CALLS[f"math.{_k}(float,float)"] = f"pys_m_{_k}:float"
# the modules a program may import; their functions and attributes are the CALLS entries and modattr()
MODULES: dict[str, bool] = {}
for _k in "sys os os.path math tempfile typing dataclasses __future__".split():
    MODULES[_k] = True
MODATTRS: dict[str, bool] = {}
for _k in "sys.argv sys.maxsize sys.stdin sys.stdout sys.stderr math.pi math.e math.inf math.tau math.nan".split():
    MODATTRS[_k] = True
TYPING: dict[str, bool] = {}
for _k in "List Dict Tuple Optional TextIO Any Union Callable Set FrozenSet Iterable Iterator Sequence Mapping Final ClassVar NamedTuple TypeVar Generic cast".split():
    TYPING[_k] = True
FUTURE: dict[str, bool] = {}
for _k in "annotations division absolute_import print_function generators nested_scopes with_statement unicode_literals generator_stop".split():
    FUTURE[_k] = True
# omitted arguments, as source text: f() -> f(default), f(x) -> f(x, default)
DEFAULTS: dict[str, str] = {"input": '""', "int": "0", "float": "0.0", "str": '""', "bool": "False",
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
# encoding= names of UTF-8 and Latin-1 (lowercase, without "-" and "_"): a str holds the file's
# bytes either way, which is what CPython's str holds for a Latin-1 file
UTF8: dict[str, bool] = {}
for _k in "utf8 u8 utf latin1 latin l1 iso88591 iso8859 8859 cp819 ibm819 csisolatin1 iso885911987 isoir100".split():
    UTF8[_k] = True
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
    "str.isupper": "bool:", "str.islower": "bool:", "str.ljust": "str:int", "str.rjust": "str:int",
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
    return t[:b] if b >= 0 else t


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
        self.ret = "None"


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

    # ---- emission helpers
    def err(self, msg: str) -> None:
        fail(msg, self.line)

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
        if t == "None" or t == "":
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
        elif k == "binop" and n.s == "|" and n.kids[1].kind == "None":
            return self.opt(self.typeof(n.kids[0]))
        elif k == "index" and n.kids[0].kind == "name":
            base = n.kids[0].s
            if base != "list" and base != "dict" and base != "tuple":
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
        self.line = d.line
        f = FnInfo(d.s, f"@f.{d.s}" if cls == "" else f"@m.{cls}.{d.s}", d, cls)
        ps = d.kids[0].kids
        if cls != "" and len(ps) == 0:
            self.err(f"method '{d.s}' of class '{cls}' must take self as its first parameter")
        for i in range(len(ps)):
            p = ps[i]
            f.params.append(p.s)
            f.defaults.append(p.kids[1])
            f.dglob.append("")
            if i == 0 and cls != "":
                f.ptypes.append(cls)
            elif p.kids[0].kind == "noann":
                self.err(f"parameter '{p.s}' of '{d.s}' needs a type annotation")
            else:
                f.ptypes.append(self.typeof(p.kids[0]))
        if d.kids[1].kind != "noann":
            f.ret = self.typeof(d.kids[1])
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
            if st.kind == "annassign" and st.kids[0].kind == "name":
                self.add_field(ci, st.kids[0].s, self.typeof(st.kids[1]))
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
            lit = ci.name + "("
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
                    t = self.typeof(st.kids[1]) if k == "annassign" else self.guess(st.kids[-1], f)
                    if t == "":
                        self.err(f"cannot infer the type of field '{name}'; annotate it (self.{name}: T = ...)")
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
            self.guard(self.ins(f"xor i1 {self.ins(f'load i1, ptr {f}')}, true"), f"AttributeError: '{o.t}' object has no attribute '{name}'")
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
        return self.modlevel or name in self.gdecl

    def load_name(self, name: str) -> Val:
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
        if name in self.fglobals:
            self.err(f"name '{name}' is not defined yet here: a function assigns it, so declare it at module level first ({name}: T)")
        self.err(f"name '{name}' is not defined")
        return Val("", "")

    def read(self, n: Node) -> Val:
        # a variable read; if flow analysis found it may be unassigned, check at run time
        name = n.s
        if n.chk and name in self.ltype:
            if name in self.lflag and name not in self.compvars:
                bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr {self.lflag[name]}')}, true")
                self.guard(bad, f"UnboundLocalError: cannot access local variable '{name}' where it is not associated with a value")
        elif n.chk and name in self.gflag and name in self.gtypes:
            bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{name}.def')}, true")
            self.guard(bad, f"NameError: name '{name}' is not defined")
        return self.load_name(name)

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
        if self.is_global(name):
            if name not in self.gtypes:
                if v.t == "None" or v.t == "":
                    self.err(f"cannot infer the type of '{name}'; add a type annotation")
                self.declare(name, v.t)
            t = self.gtypes[name]
            self.emit(f"store {lt(t)} {self.coerce(v, t).v}, ptr @g.{name}")
            if name in self.gflag:
                self.emit(f"store i1 true, ptr @g.{name}.def")
        else:
            if name not in self.ltype:
                self.alloca(v.t, name)
            t = self.ltype[name]
            self.emit(f"store {lt(t)} {self.coerce(v, t).v}, ptr {self.lreg[name]}")
            if name in self.lflag and name not in self.compvars:
                self.emit(f"store i1 true, ptr {self.lflag[name]}")

    def names_in(self, t: Node, out: list[str]) -> None:
        if t.kind == "name":
            out.append(t.s)
        elif t.kind == "tuple":
            for k in t.kids:
                self.names_in(k, out)

    def collect(self, body: list[Node], out: dict[str, bool]) -> None:
        # Python's rule: a name assigned anywhere in a function is local to it
        for st in body:
            k = st.kind
            if k == "assign" or k == "annassign" or k == "augassign" or k == "for" or k == "with":
                names: list[str] = []
                if k == "with":
                    for it in st.kids[:-1]:
                        if len(it.kids) == 2:
                            self.names_in(it.kids[1], names)
                for i in range(len(st.kids) - 1 if k == "assign" else 0 if k == "with" else 1):
                    self.names_in(st.kids[i], names)
                for nm in names:
                    out[nm] = True
            for kid in st.kids:
                if kid.kind == "block":
                    self.collect(kid.kids, out)

    def globals_in(self, body: list[Node], out: dict[str, bool]) -> None:
        for st in body:
            if st.kind == "global":
                for nm in st.kids:
                    out[nm.s] = True
            for kid in st.kids:
                if kid.kind == "block":
                    self.globals_in(kid.kids, out)

    def target_type(self, n: Node) -> str:
        # expected type of an assignment target (types empty [] / {} literals): a name, or a
        # chain of attributes and subscripts on one (g.groups["a"], d["x"]["y"])
        if n.kind == "name":
            return self.ltype.get(n.s, self.gtypes.get(n.s, "") if self.is_global(n.s) else "")
        if n.kind == "slice":
            self.err("assignment to a slice is not supported")
        if n.kind == "attr" or n.kind == "index":
            t = self.target_type(n.kids[0])
            if n.kind == "attr" and t in self.classes:
                return self.classes[t].ftypes.get(n.s, "")
            if n.kind == "index" and is_list(t):
                return elem(t)
            if n.kind == "index" and is_dict(t):
                return targs(t)[1]
        return ""

    def assign(self, t: Node, v: Val) -> None:
        k = t.kind
        if k == "name":
            self.store_name(t.s, v)
        elif k == "attr":
            o = self.expr(t.kids[0], "")
            self.setfield(o, self.field(o, t.s, True), t.s, v)
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
        self.cold = {}
        self.nn = {}
        self.selfname = ""
        self.uflags = f.uflags
        self.lflag = {}
        self.line = f.node.line
        if not self.modlevel:
            self.collect(body, self.assigned)
        ps: list[str] = []
        if f.cls != "":
            # callers check the receiver, so self is never None inside a method
            self.nn["%a0"] = True
            if f.params[0] not in self.assigned:
                self.selfname = f.params[0]
        for i in range(len(f.params)):
            t = f.ptypes[i]
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
        self.stmts(body)
        if not self.term:
            if f.ret == "None":
                self.emit("ret void")
            else:
                self.raise_("RuntimeError", self.sconst(f"{f.name}() ended without returning a value"))
        for msg in self.cold:
            self.place(self.cold[msg])
            i = msg.find(": ")
            self.raise_(msg[:i], self.sconst(msg[i + 2 :]))
        self.out.append(f"define internal {lt(f.ret)} {f.ll}({', '.join(ps)}) {{")
        self.out.append("entry:")
        self.out.extend(self.allocas)
        self.out.extend(self.body)
        self.out.append("}")

    def module(self, m: Node) -> str:
        top: list[Node] = []
        self.scan_imports(m.kids)
        for st in m.kids:
            if st.kind == "class":
                self.line = st.line
                if st.s in self.classes:
                    self.err(f"redefinition of class '{st.s}' is not supported")
                self.classes[st.s] = ClassInfo(st.s, st)
                if len(st.kids) > 1 and self.imported(st.kids[1].s) != "dataclasses.dataclass":
                    self.err(f"unsupported decorator @{st.kids[1].s} (import dataclass from dataclasses)")
        for st in m.kids:
            self.line = st.line
            if st.kind == "def":
                if st.s in self.funcs or st.s in self.classes:
                    self.err(f"redefinition of '{st.s}' is not supported")
                self.funcs[st.s] = self.declare_fn(st, "")
                top.append(mk("defaults", st.s, st.line, []))
            elif st.kind == "class":
                for d in st.kids[0].kids:
                    if d.kind == "def":
                        self.line = d.line
                        if d.s in self.classes[st.s].methods:
                            self.err(f"redefinition of method '{st.s}.{d.s}' is not supported")
                        self.classes[st.s].methods[d.s] = self.declare_fn(d, st.s)
                top.append(mk("cdefaults", st.s, st.line, []))
            else:
                top.append(st)
        for ci in self.classes.values():
            self.declare_fields(ci)
            for f in ci.methods.values():
                self.check_special(f)
        self.flow_program(top)
        for nm in self.gflag:
            if nm in self.funcs or nm in self.classes:
                self.global_var(f"@g.{nm}.def", "i1")
        self.modlevel = True
        self.function(FnInfo("<module>", "@main.init", m, ""), top)
        self.modlevel = False
        for f in self.funcs.values():
            self.function(f, f.node.kids[2].kids)
        for ci in self.classes.values():
            for f in ci.methods.values():
                if f.ll not in self.lazy:
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
    def flow_program(self, top: list[Node]) -> None:
        fns: list[FnInfo] = []
        for f in self.funcs.values():
            fns.append(f)
        for ci in self.classes.values():
            for f in ci.methods.values():
                fns.append(f)
        gl: dict[str, bool] = {}
        self.collect(top, gl)
        for f in fns:
            decl: dict[str, bool] = {}
            asg: dict[str, bool] = {}
            self.globals_in(f.node.kids[2].kids, decl)
            self.collect(f.node.kids[2].kids, asg)
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
        # def and class statements bind their names when they run: calls that may come first are checked
        for nm in self.funcs:
            gl[nm] = True
        for nm in self.classes:
            gl[nm] = True
        mfl = Flow(gl, {}, True)
        self.fl_stmts(mfl, top)
        self.gflag = mfl.marks
        # functions run only from module code: globals assigned before its first call into user
        # code stay assigned while any function runs
        safe = mfl.call if mfl.called else gl
        for f in fns:
            body = f.node.kids[2].kids
            loc: dict[str, bool] = {}
            decl: dict[str, bool] = {}
            self.collect(body, loc)
            self.globals_in(body, decl)
            tracked = dict(gl)
            defd: dict[str, bool] = {}
            for nm in loc:
                tracked[nm] = True
            for nm in gl:
                if nm in safe and (nm not in loc or nm in decl):
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
            self.collect(init.node.kids[2].kids, asg)
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

    def user_call(self, n: Node) -> bool:
        # may running n call a user function, method or constructor?
        if n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s in self.funcs or n.kids[0].s in self.classes):
            return True
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
            pre = dict(fl.defd)
            outer = fl.brks
            fl.brks = []
            if k == "for":
                self.fl_target(fl, n.kids[0])
            self.fl_stmts(fl, n.kids[-1].kids)
            brks = fl.brks
            fl.brks = outer
            fl.defd = pre
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
        elif not self.known_path(tgt):
            self.err(f"cannot import name '{x}' from '{mod}' (not supported by Pystachy)")

    def known_path(self, p: str) -> bool:
        # a module attribute Pystachy implements: a CALLS entry, a modattr() value, a module, or
        # a function builtin() handles itself
        if p in MODULES or p in MODATTRS or p == "sys.exit":
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
                f.dglob[j] = self.hidden(f"@d.{f.ll[1:]}.{f.params[j]}", self.coerce(self.expr(d, t), t))

    def hoist_class(self, ci: ClassInfo) -> None:
        # class-body defaults are evaluated once, when the class statement runs, in body order,
        # and shared. Pystachy has no class scope: names bound earlier in the body are rejected.
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

    def loop(self, body: list[Node], cont: str, brk: str) -> None:
        self.loops.append(cont)
        self.loops.append(brk)
        self.wdepth.append(len(self.withs))
        self.stmts(body)
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
        if name == "SystemExit":
            self.exit_(vals)
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
            if len(n.kids) == 2 and t0.kind == "tuple" and (val.kind == "tuple" or val.kind == "list") and len(t0.kids) == len(val.kids):
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
            t = self.typeof(n.kids[1])
            if n.kids[0].kind == "name":
                self.declare(n.kids[0].s, t)
            if len(n.kids) == 3:
                self.assign(n.kids[0], self.coerce(self.expr(n.kids[2], t), t))
        elif k == "augassign":
            self.augassign(n)
        elif k == "if":
            c = self.cond(n.kids[0])
            l1 = self.label()
            l2 = self.label()
            l3 = self.label()
            self.cbr(c, l1, l2)
            self.place(l1)
            self.stmts(n.kids[1].kids)
            self.br(l3)
            self.place(l2)
            self.stmts(n.kids[2].kids)
            self.place(l3)
        elif k == "while":
            l1 = self.label()
            l2 = self.label()
            l3 = self.label()
            self.place(l1)
            self.cbr(self.cond(n.kids[0]), l2, l3)
            self.place(l2)
            self.loop(n.kids[1].kids, l1, l3)
            self.br(l1)
            self.place(l3)
        elif k == "for":
            self.for_(n, [])
        elif k == "return":
            if self.modlevel:
                self.err("'return' outside function")
            if len(n.kids) == 0 or (self.ret == "None" and n.kids[0].kind == "None"):
                if self.ret != "None":
                    self.err(f"missing return value of type {self.ret}")
                self.close_withs(0)
                self.emit("ret void")
            else:
                if self.ret == "None":
                    self.err("returning a value from a function without a return annotation")
                v = self.coerce(self.expr(n.kids[0], self.ret), self.ret)
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
            dt = n.kids[0]
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
        elif k == "def" or k == "class":
            self.err("nested functions and classes are not supported")
        elif k != "pass":
            self.err(f"unsupported statement '{k}'")

    def augassign(self, n: Node) -> None:
        t = n.kids[0]
        op = n.s
        if t.kind == "name":
            cur = self.read(t)
            self.store_name(t.s, self.inplace(op, cur, n.kids[1]))
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
        if it.kind == "call" and it.kids[0].kind == "name" and it.kids[0].s not in self.ltype:
            fn = it.kids[0].s
            args = it.kids[1:]
            if fn == "range":
                vs = self.range_args(args)
                self.for_range(tgt, vs[0], vs[1], vs[2], body, hide)
                return
            if fn == "reversed" and len(args) == 1 and args[0].kind == "call" and args[0].kids[0].kind == "name" and args[0].kids[0].s == "range" and "range" not in self.ltype:
                self.for_rrange(tgt, self.range_args(args[0].kids[1:]), body, hide)
                return
            if ((fn == "enumerate" or fn == "reversed") and len(args) == 1) or (fn == "zip" and len(args) > 0):
                seqs = [self.expr(a, "") for a in args]
                self.for_seq(tgt, seqs, fn, body, "0", hide)
                for i in range(len(args)):
                    self.close_temp(args[i], seqs[i])
                return
            if fn == "enumerate" and len(args) == 2 and (args[1].kind != "kw" or args[1].s == "start"):
                seq = self.expr(args[0], "")
                a1 = args[1].kids[0] if args[1].kind == "kw" else args[1]
                self.for_seq(tgt, [seq], fn, body, self.coerce(self.expr(a1, "int"), "int").v, hide)
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
        seq = self.expr(it, "")
        self.for_seq(tgt, [seq], "", body, "0", hide)
        self.close_temp(it, seq)

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
                    j = self.rt("pys_dict_prev", "i64", [f"ptr {s.v}", f"i64 {p}", f"i64 {used[k]}"])
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

    # ---- expressions
    def cond(self, n: Node) -> str:
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
            return "true"
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
            et = elem(want) if is_list(want) else ""
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
            kv = targs(want) if is_dict(want) else ["", ""]
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
            if len(vals) == 0:
                self.err("empty tuples are not supported")
            return self.tuple_(vals)
        if k == "listcomp":
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
        self.names_in(n.kids[1], names)
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
        c = self.cond(n.kids[0])
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(c, l1, l2)
        self.place(l1)
        a = self.expr(n.kids[1], want)
        e1 = self.cur
        self.br(l3)
        self.place(l2)
        b = self.expr(n.kids[2], want if want != "" else a.t)
        t = b.t if a.t == "None" else a.t
        b = self.coerce(b, t)
        if t == "None":
            self.err("conditional expression has no value")
        e2 = self.cur
        self.br(l3)
        self.place(l3)
        return Val(self.ins(f"phi {lt(t)} [{a.v}, %{e1}], [{b.v}, %{e2}]"), t)

    def boolop(self, n: Node, ascond: bool, want: str) -> Val:
        # Python semantics: `a or b` yields a if a is truthy, else b (same static type)
        a = Val(self.cond(n.kids[0]), "bool") if ascond else self.expr(n.kids[0], want)
        c = self.truth(a)
        e1 = self.cur
        l2 = self.label()
        l3 = self.label()
        if n.s == "and":
            self.cbr(c, l2, l3)
        else:
            self.cbr(c, l3, l2)
        self.place(l2)
        b = Val(self.cond(n.kids[1]), "bool") if ascond else self.coerce(self.expr(n.kids[1], a.t), a.t)
        e2 = self.cur
        self.br(l3)
        self.place(l3)
        return Val(self.ins(f"phi {lt(a.t)} [{a.v}, %{e1}], [{b.v}, %{e2}]"), a.t)

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
        if op == "is" or op == "is not":
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
            if not iv.v.startswith("%") and abs(int(iv.v)) <= 9007199254740992:
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
        if f.kind == "name" and f.s not in self.ltype:
            if f.chk and f.s in self.gflag:
                # a call that may run before the def or class statement
                bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{f.s}.def')}, true")
                self.guard(bad, f"NameError: name '{f.s}' is not defined")
            if f.s in self.funcs:
                return self.call_fn(self.funcs[f.s], [], args)
            if f.s in self.aliases and f.s not in self.gtypes:
                return self.builtin(self.aliases[f.s], args, want)
            if f.s in self.classes:
                size = f"ptrtoint (ptr getelementptr (%C.{f.s}, ptr null, i32 1) to i64)"
                o = Val(self.rt("pys_alloc", "ptr", [f"i64 {size}"]), f.s)
                self.nn[o.v] = True
                self.call_fn(self.classes[f.s].methods["__init__"], [o], args)
                return o
            return self.builtin(f.s, args, want)
        if f.kind == "attr":
            path = self.dotted(f)
            if path != "" and path[: path.rfind(".")] not in MODATTRS:
                return self.builtin(path, args, want)
            o = self.expr(f.kids[0], "")
            r = self.method(o, f.s, args)
            if f.s != "close":
                self.close_temp(f.kids[0], o)
            return r
        self.err("only functions, classes and methods can be called")
        return Val("", "")

    def open_call(self, n: Node) -> bool:
        return n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s == "open" and "open" not in self.ltype and "open" not in self.funcs

    def close_temp(self, n: Node, v: Val) -> None:
        # open(p).read(): nothing else refers to the file, so CPython closes it right after its use
        if v.t == "file" and self.open_call(n):
            self.rt("pys_file_close", "void", [f"ptr {v.v}"])

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
        if e.kind == "str" and e.s.lower().replace("-", "").replace("_", "") not in UTF8:
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

    def call_fn(self, f: FnInfo, pre: list[Val], args: list[Node]) -> Val:
        self.called[f.ll] = True
        np = len(f.params)
        vals: list[Val] = []
        for i in range(np):
            vals.append(self.coerce(pre[i], f.ptypes[i]) if i < len(pre) else Val("", ""))
        pos = len(pre)
        for a in args:
            j = pos
            e = a
            if a.kind == "kw":
                if a.s not in f.params:
                    self.err(f"{f.name}() got an unexpected keyword argument '{a.s}'")
                j = f.params.index(a.s)
                e = a.kids[0]
            else:
                pos += 1
            if j >= np:
                self.err(f"too many arguments in call to {f.name}()")
            if vals[j].t != "":
                self.err(f"{f.name}() got multiple values for argument '{f.params[j]}'")
            vals[j] = self.coerce(self.expr(e, f.ptypes[j]), f.ptypes[j])
        for j in range(np):
            if vals[j].t == "":
                if f.defaults[j].kind == "noann":
                    self.err(f"missing argument '{f.params[j]}' in call to {f.name}()")
                t = f.ptypes[j]
                if f.dglob[j] != "":
                    vals[j] = Val(self.ins(f"load {lt(t)}, ptr {f.dglob[j]}"), t)
                else:
                    vals[j] = self.coerce(self.expr(f.defaults[j], t), t)
        call = f"call {lt(f.ret)} {f.ll}({', '.join([lt(v.t) + ' ' + v.v for v in vals])})"
        if f.ret == "None":
            self.emit(call)
            return Val("null", "None")
        return Val(self.ins(call), f.ret)

    def dotted(self, n: Node) -> str:
        # "sys.argv", "os.path.exists", ... when n is an attribute chain on a module
        if n.kind == "name":
            if n.s in self.aliases and n.s not in self.ltype and n.s not in self.gtypes and n.s not in self.compvars:
                return self.aliases[n.s]
        elif n.kind == "attr":
            p = self.dotted(n.kids[0])
            if p != "":
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
        # builtins and module functions ("os.system"); most are one call listed in CALLS
        if name == "print":
            return self.print_(args)
        if name == "open":
            return self.open_(args)
        if name == "map" or name == "filter":
            self.err(f"{name}() is not supported; use a list comprehension")
        if (name == "any" or name == "all") and len(args) == 1 and args[0].kind == "listcomp" and args[0].s == "gen":
            return self.listcomp(args[0], "", name)
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
            fresh = self.iterator_call(args[0])
            v0 = self.consume(args[0], w)
            vals = [self.as_list(v0, name)]
            self.close_temp(args[0], v0)
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
        if name == "sys.exit" or name == "exit" or name == "quit":
            if len(vals) > 1:
                self.err(f"sys.exit() takes at most 1 argument ({len(vals)} given)")
            self.exit_(vals)
            return Val("null", "None")
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
            return Val(self.rt("pys_dict_copy", "ptr", [f"ptr {v.v}"]), t)
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
        if n.kind != "call" or n.kids[0].kind != "name" or n.kids[0].s in self.ltype or n.kids[0].s in self.funcs:
            return False
        fn = n.kids[0].s
        return fn == "range" or fn == "reversed" or fn == "enumerate" or fn == "zip"

    def consume(self, n: Node, want: str) -> Val:
        # range(), reversed(), enumerate() and zip() where their items are used at once (list(),
        # sorted(), "".join(), ...) become a fresh list of those items, built by the for loop
        # machinery; anywhere else they are rejected, as a list would print differently
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
        if v.t == "str" and (name == "sorted" or name == "min" or name == "max"):
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
            if i < len(args):
                v = self.coerce(self.consume(args[i], pt) if key == "str.join" else self.expr(args[i], pt), pt)
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
            # object.__repr__: <__main__.Name object at 0x...>
            r = Val(self.rt("pys_default_repr", "ptr", [f"ptr {self.sconst(v.t)}", f"ptr {v.v}"]), "str")
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
def compile_source(src: str) -> str:
    return Gen().module(Parser(Lexer(src, 1).run()).module())


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
    f = open(SRC, "r", encoding="latin-1")
    ir = compile_source(f.read())
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
    home = os.getenv("PYSTACHY_HOME", "")
    if home == "":
        s = argv[0].rfind("/")
        home = argv[0][:s] if s >= 0 else "."
        if not os.path.exists(home + "/runtime.c"):
            home = home + "/.."
    rtc = home + "/runtime.c"
    # PYSTACHY_CFLAGS: extra clang flags (e.g. -fsanitize=undefined) for the runtime and the AOT link;
    # each flag set caches its own runtime bitcode, named by a 32-bit FNV-1a hash of the flags
    flags = os.getenv("PYSTACHY_CFLAGS", "").split()
    key = 2166136261
    for c in " ".join(flags):
        key = ((key ^ ord(c)) * 16777619) & 0xFFFFFFFF
    rtb = home + ("/build/runtime.bc" if len(flags) == 0 else f"/build/runtime-{key:08x}.bc")
    cflags = "".join([" " + q(a) for a in flags])
    llvm = os.getenv("PYSTACHY_LLVM", "")  # optional directory holding clang, opt, lli, llvm-link, llvm-as
    if llvm != "" and not llvm.endswith("/"):
        llvm = llvm + "/"
    # strip clang's target-cpu/features attributes so LLVM can inline runtime helpers into our code
    strip = "sed -E 's/ \"(target-cpu|target-features|tune-cpu)\"=\"[^\"]*\"//g'"
    # intermediate files go to a private directory (mode 0700, honours TMPDIR), removed on every path below
    tmp = tempfile.mkdtemp()
    ll = tmp + "/prog.ll"
    bc = tmp + "/prog.bc"
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
        code = sh(f"{link} && {llvm}clang -O2 {q(bc)} -o {q(out)} -lm{cflags}")
    else:
        # JIT tier: cheap SSA cleanup of the program alone, then LLVM's ORC JIT compiles it for the
        # host CPU and links it with the precompiled runtime (the JIT tier never inlines the runtime)
        fast = f"{llvm}opt -passes='mem2reg,instcombine<no-verify-fixpoint>,simplifycfg'"
        code = sh(f"{fast} {q(ll)} -o {q(bc)} && PYSTACHY_ARGV0={q(SRC)} {llvm}lli -extra-object={q(rto)} {q(bc)} {' '.join([q(a) for a in rest])}")
    for p in [ll, bc, rll, part]:
        if os.path.exists(p):
            os.remove(p)
    os.rmdir(tmp)
    if msg != "":
        fail(msg, 0)
    sys.exit(code)


if __name__ == "__main__":
    main()
