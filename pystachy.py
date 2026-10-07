"""Pystachy: a self-hosting compiler for a statically typed subset of Python.

source -> Lexer -> Parser (AST) -> Gen (type check + LLVM IR in one pass) -> LLVM
`pystachy run` JIT-executes the program with lli (ORC); `pystachy build` compiles it AOT
with clang. This file is itself written in the Pystachy subset and compiles itself.
"""
from __future__ import annotations
import sys
import os

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
        if src.startswith("0x", j) or src.startswith("0X", j):
            j += 2
            while j < len(src) and (src[j].isalnum() or src[j] == "_"):
                j += 1
            h = src[self.i + 2 : j].replace("_", "").lstrip("0")
            if len(h) > 16 or (len(h) == 16 and h[0] > "7"):
                fail("integer literal does not fit in 64 bits", self.line)
            self.add("int", str(int("0" + h, 16)))
            self.i = j
            return
        isf = False
        while j < len(src) and (src[j].isdigit() or src[j] == "_"):
            j += 1
        if src.startswith(".", j) and not src.startswith("..", j):
            isf = True
            j += 1
            while j < len(src) and src[j].isdigit():
                j += 1
        if j < len(src) and (src[j] == "e" or src[j] == "E"):
            isf = True
            j += 1
            if src[j] == "+" or src[j] == "-":
                j += 1
            while j < len(src) and src[j].isdigit():
                j += 1
        self.add("float" if isf else "int", src[self.i : j].replace("_", ""))
        self.i = j

    def word(self) -> None:
        src = self.src
        j = self.i
        while j < len(src) and (src[j].isalnum() or src[j] == "_" or ord(src[j]) >= 128):
            j += 1
        w = src[self.i : j]
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
        out: list[str] = []
        while True:
            if self.i >= len(src):
                fail("unterminated string", line)
            c = src[self.i]
            if c == q and (not triple or src.startswith(q + q + q, self.i)):
                self.i += 3 if triple else 1
                break
            if c == "\n":
                if not triple:
                    fail("unterminated string", line)
                self.line += 1
            if c == "\\" and "r" not in prefix:
                e = src[self.i + 1]
                self.i += 2
                if e == "\n":
                    self.line += 1
                elif e == "x":
                    out.append(chr(int(src[self.i : self.i + 2], 16)))
                    self.i += 2
                elif e >= "0" and e <= "7":
                    v = ord(e) - 48
                    for _ in range(2):
                        if self.i < len(src) and src[self.i] >= "0" and src[self.i] <= "7":
                            v = v * 8 + ord(src[self.i]) - 48
                            self.i += 1
                    out.append(chr(v & 255))
                elif e in ESCAPES:
                    out.append(ESCAPES[e])
                else:
                    out.append("\\" + e)
                continue
            out.append(c)
            self.i += 1
        self.toks.append(Tok("fstr" if "f" in prefix else "str", "".join(out), line))

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


def mk(kind: str, s: str, line: int, kids: list[Node]) -> Node:
    n = Node(kind, s, line)
    n.kids = kids
    return n


STARTS: dict[str, bool] = {}
for _k in "id int float str fstr ( [ { - + ~ not None True False lambda".split():
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
            name = self.expect("id").text
            self.expect("nl")
            self.stmt(out)
            d = out[-1]
            if name != "dataclass" or d.kind != "class":
                fail(f"unsupported decorator @{name}", line)
            d.kids.append(mk("deco", name, line, []))
        elif k == "try" or k == "with" or k == "async":
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
        while not self.eat(")"):
            if self.peek() == "*" or self.peek() == "**" or self.peek() == "/":
                fail("*args, **kwargs and positional-only markers are not supported", line)
            pname = self.expect("id").text
            ann = mk("noann", "", line, [])
            dflt = mk("noann", "", line, [])
            if self.eat(":"):
                ann = self.test()
            if self.eat("="):
                dflt = self.test()
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
            return mk("raise", "", line, [self.test()])
        if k == "del":
            self.p += 1
            return mk("del", "", line, [self.test()])
        if k == "nonlocal" or k == "yield":
            fail(f"'{k}' is not supported", line)
        e = self.exprlist()
        if self.eat(":"):
            n = mk("annassign", "", line, [e, self.test()])
            if self.eat("="):
                n.kids.append(self.exprlist())
            return n
        if self.peek() == "=":
            n = mk("assign", "", line, [e])
            while self.eat("="):
                n.kids.append(self.exprlist())
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
        e = self.test()
        if self.peek() != ",":
            return e
        t = mk("tuple", "", line, [e])
        while self.eat(","):
            if self.peek() not in STARTS:
                break
            t.kids.append(self.test())
        return t

    def targets(self) -> Node:
        line = self.line()
        e = self.postfix()
        if self.peek() != ",":
            return e
        t = mk("tuple", "", line, [e])
        while self.eat(","):
            if self.peek() == "in":
                break
            t.kids.append(self.postfix())
        return t

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
                while not self.eat(")"):
                    if self.peek() == "*" or self.peek() == "**":
                        fail("star arguments are not supported", line)
                    if self.peek() == "id" and self.ahead() == "=":
                        name = self.toks[self.p].text
                        self.p += 2
                        c.kids.append(mk("kw", name, line, [self.test()]))
                    else:
                        a = self.test()
                        if self.peek() == "for":
                            a = self.comp(a, line)
                        c.kids.append(a)
                    if not self.eat(","):
                        self.expect(")")
                        break
                e = c
            elif self.eat("["):
                lo = mk("omit", "", line, [])
                if self.peek() != ":":
                    lo = self.test()
                if self.eat(":"):
                    hi = mk("omit", "", line, [])
                    if self.peek() != "]":
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
        if k == "str":
            s = t.text
            while self.peek() == "str":
                s = s + self.toks[self.p].text
                self.p += 1
            return mk("str", s, line, [])
        if k == "fstr":
            return self.fstring(t)
        if k == "None" or k == "True" or k == "False":
            return mk(k, "", line, [])
        if k == "(":
            if self.eat(")"):
                return mk("tuple", "", line, [])
            e = self.test()
            if self.peek() == "for":
                e = self.comp(e, line)
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

    def fstring(self, t: Tok) -> Node:
        s = t.text
        n = mk("fstr", "", t.line, [])
        lit: list[str] = []
        i = 0
        while i < len(s):
            c = s[i]
            if (c == "{" or c == "}") and s[i + 1 : i + 2] == c:
                lit.append(c)
                i += 2
            elif c == "{":
                j = i + 1
                depth = 0
                while j < len(s) and (depth > 0 or not (s[j] == "}" or s[j] == ":" or (s[j] == "!" and s[j + 1 : j + 2] != "="))):
                    if s[j] == "'" or s[j] == '"':
                        j = s.find(s[j], j + 1)
                        if j < 0:
                            fail("bad f-string", t.line)
                    elif s[j] == "(" or s[j] == "[" or s[j] == "{":
                        depth += 1
                    elif s[j] == ")" or s[j] == "]" or s[j] == "}":
                        depth -= 1
                    j += 1
                if j >= len(s):
                    fail("unterminated '{' in f-string", t.line)
                if len(lit) > 0:
                    n.kids.append(mk("str", "".join(lit), t.line, []))
                    lit = []
                e = Parser(Lexer(s[i + 1 : j], t.line).run()).test()
                if s[j] == "!":
                    if s[j + 1 : j + 2] == "r":
                        e = mk("call", "", t.line, [mk("name", "repr", t.line, []), e])
                    j += 2
                if s[j] == ":":
                    k = s.find("}", j)
                    if k < 0:
                        fail("unterminated '{' in f-string", t.line)
                    e = mk("fmt", s[j + 1 : k], t.line, [e])
                    j = k
                n.kids.append(e)
                i = j + 1
            else:
                lit.append(c)
                i += 1
        if len(lit) > 0:
            n.kids.append(mk("str", "".join(lit), t.line, []))
        return n


# ---------------------------------------------------------------- types
# A type is a canonical string: int float bool str None file, list[T], dict[K,V],
# tuple[A,B], or a class name. LLVM view: i64, double, i1, void, everything else ptr.
HEX = "0123456789ABCDEF"
IOPS: dict[str, str] = {"&": "and", "|": "or", "^": "xor"}
CHECKED: dict[str, str] = {"+": "sadd", "-": "ssub", "*": "smul"}  # llvm.*.with.overflow
IRT: dict[str, str] = {"//": "pys_floordiv", "%": "pys_mod", "**": "pys_pow", "<<": "pys_shl", ">>": "pys_shr"}
FOPS: dict[str, str] = {"+": "fadd", "-": "fsub", "*": "fmul"}
FRT: dict[str, str] = {"/": "pys_fdiv", "//": "pys_ffloordiv", "%": "pys_fmod", "**": "pow"}
ICMP: dict[str, str] = {"==": "eq", "!=": "ne", "<": "slt", "<=": "sle", ">": "sgt", ">=": "sge"}
FCMP: dict[str, str] = {"==": "oeq", "!=": "une", "<": "olt", "<=": "ole", ">": "ogt", ">=": "oge"}
DUNDER: dict[str, str] = {"+": "__add__", "-": "__sub__", "*": "__mul__", "/": "__truediv__", "//": "__floordiv__", "%": "__mod__",
                          "==": "__eq__", "!=": "__ne__", "<": "__lt__", "<=": "__le__", ">": "__gt__", ">=": "__ge__"}
# builtin and module functions that are one runtime call: "name(argtypes)": "C function:result type"
CALLS: dict[str, str] = {
    "ord(str)": "pys_ord:int", "chr(int)": "pys_chr:str", "int(float)": "pys_f2i:int", "int(str,int)": "pys_int_str:int",
    "float(str)": "pys_float_str:float", "round(float)": "pys_round:int", "round(float,int)": "pys_round_n:float", "input(str)": "pys_input:str",
    "abs(float)": "fabs:float", "list(str)": "pys_str_list:list[str]", "dict(dict)": "pys_dict_copy:",
    "sum(list[int])": "pys_sum_int:int", "sum(list[float])": "pys_sum_float:float", "any(list[bool])": "pys_any:bool",
    "all(list[bool])": "pys_all:bool", "any(list[int])": "pys_any:bool", "all(list[int])": "pys_all:bool",
    "open(str,str)": "pys_open:file", "sys.exit(int)": "pys_exit:None", "sys.stdout.flush()": "pys_flush:None",
    "sys.stdout.write(str)": "pys_out:int", "sys.stderr.write(str)": "pys_err:int", "os.system(str)": "pys_system:int",
    "os.getpid()": "pys_getpid:int", "os.path.exists(str)": "pys_exists:bool", "os.getenv(str,str)": "pys_getenv:str",
    "math.floor(float)": "pys_floor:int", "math.ceil(float)": "pys_ceil:int", "math.pow(float,float)": "pow:float",
    "math.atan2(float,float)": "atan2:float", "math.hypot(float,float)": "hypot:float", "math.fmod(float,float)": "fmod:float",
}
for _k in "sqrt sin cos tan asin acos atan sinh cosh tanh exp log log2 log10 fabs".split():
    CALLS[f"math.{_k}(float)"] = _k + ":float"
# the modules a program may import; their functions and attributes are the CALLS entries and modattr()
MODULES: dict[str, bool] = {}
for _k in "sys os os.path math typing dataclasses __future__".split():
    MODULES[_k] = True
# omitted arguments, as source text: f() -> f(default), f(x) -> f(x, default)
DEFAULTS: dict[str, str] = {"input": '""', "sys.exit": "0", "int": "0", "float": "0.0", "str": '""', "bool": "False",
                            "list": "[]", "dict": "{}", "int(str)": "10", "open(str)": '"r"'}
# Builtin methods, "ret:arg,arg=default". *X: passed/returned as an 8-byte slot; #: element
# type descriptor; T: list element, K/V: dict key/value, S: the receiver's own type.
# Each maps to the C function pys_<type>_<method>.
METHODS: dict[str, str] = {
    "str.join": "str:list[str]", "str.split": "list[str]:str=null", "str.strip": "str:str=null",
    "str.lstrip": "str:str=null", "str.rstrip": "str:str=null", "str.startswith": "bool:str,int=0",
    "str.endswith": "bool:str", "str.find": "int:str,int=0", "str.rfind": "int:str", "str.index": "int:str",
    "str.count": "int:str", "str.replace": "str:str,str", "str.upper": "str:", "str.lower": "str:",
    "str.isdigit": "bool:", "str.isalpha": "bool:", "str.isalnum": "bool:", "str.isspace": "bool:",
    "str.isupper": "bool:", "str.islower": "bool:", "str.ljust": "str:int", "str.rjust": "str:int",
    "list.append": "None:*T", "list.pop": "*T:int=-1", "list.insert": "None:int,*T", "list.extend": "None:S",
    "list.index": "int:*T,#", "list.count": "int:*T,#", "list.remove": "None:*T,#", "list.reverse": "None:",
    "list.sort": "None:#", "list.copy": "S:", "list.clear": "None:",
    "dict.get": "*V:*K,*V=0", "dict.pop": "*V:*K", "dict.setdefault": "*V:*K,*V", "dict.keys": "list[K]:",
    "dict.values": "list[V]:", "dict.items": "list[tuple[K,V]]:", "dict.clear": "None:", "dict.copy": "S:",
    "file.read": "str:", "file.readline": "str:", "file.write": "int:str", "file.close": "None:",
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
        self.ret = "None"


class ClassInfo:
    def __init__(self, name: str, node: Node):
        self.name = name
        self.node = node
        self.fields: list[str] = []
        self.ftypes: dict[str, str] = {}
        self.fdefault: dict[str, Node] = {}
        self.fglob: dict[str, str] = {}
        self.methods: dict[str, FnInfo] = {}


# ---------------------------------------------------------------- code generator
class Gen:
    def __init__(self):
        self.classes: dict[str, ClassInfo] = {}
        self.funcs: dict[str, FnInfo] = {}
        self.aliases: dict[str, str] = {}
        self.gtypes: dict[str, str] = {}
        self.globs: list[str] = []
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
        self.lcs: list[str] = []
        self.lct: list[str] = []
        self.ret = "None"
        self.cold: dict[str, str] = {}
        self.nn: dict[str, bool] = {}
        self.selfname = ""
        self.lazy: dict[str, FnInfo] = {}
        self.called: dict[str, bool] = {}
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
        return "O"

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
            if s == "TextIO":
                return "file"
        elif k == "binop" and n.s == "|" and n.kids[1].kind == "None":
            return self.opt(self.typeof(n.kids[0]))
        elif k == "index" and n.kids[0].kind == "name":
            base = n.kids[0].s.lower()
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

    def opt(self, t: str) -> str:
        if t not in self.classes:
            self.err(f"None/Optional is only supported for class types, not {t}")
        return t

    def declare_fn(self, d: Node, cls: str) -> FnInfo:
        self.line = d.line
        f = FnInfo(d.s, f"@f.{d.s}" if cls == "" else f"@m.{cls}.{d.s}", d, cls)
        ps = d.kids[0].kids
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
        for st in ci.node.kids[0].kids:
            self.line = st.line
            if st.kind == "annassign" and st.kids[0].kind == "name":
                self.add_field(ci, st.kids[0].s, self.typeof(st.kids[1]))
                if len(st.kids) == 3:
                    ci.fdefault[st.kids[0].s] = st.kids[2]
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
                parts.append(mk("call", "", line, [mk("name", "repr", line, []), mk("attr", ci.fields[i], line, [me])]))
                lit = ""
            parts.append(mk("str", lit + ")", line, []))
            self.synth(ci, "__repr__", "str", [mk("return", "", line, [mk("fstr", "", line, parts)])])
        if "__eq__" not in ci.methods:
            test = mk("True", "", line, [])
            for i in range(len(ci.fields)):
                c = mk("cmp", "==", line, [mk("attr", ci.fields[i], line, [me]), mk("attr", ci.fields[i], line, [other])])
                test = c if i == 0 else mk("boolop", "and", line, [test, c])
            isnone = mk("cmp", "is", line, [other, mk("None", "", line, [])])
            no = mk("block", "", line, [mk("return", "", line, [mk("False", "", line, [])])])
            self.synth(ci, "__eq__", "bool", [mk("if", "", line, [isnone, no, mk("block", "", line, [])]), mk("return", "", line, [test])])

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
        return ""

    def field(self, o: Val, name: str) -> Val:
        if o.t not in self.classes:
            self.err(f"type {o.t} has no attribute '{name}'")
        ci = self.classes[o.t]
        if name not in ci.ftypes:
            self.err(f"'{o.t}' object has no attribute '{name}'")
        self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{name}'")
        i = ci.fields.index(name)
        return Val(self.ins(f"getelementptr %C.{o.t}, ptr {o.v}, i32 0, i32 {i}"), ci.ftypes[name])

    # ---- variables
    def is_global(self, name: str) -> bool:
        if name in self.ltype or name in self.compvars:
            return False
        return self.modlevel or name in self.gdecl

    def load_name(self, name: str) -> Val:
        if name in self.ltype:
            t = self.ltype[name]
            r = self.ins(f"load {lt(t)}, ptr {self.lreg[name]}")
            if name == self.selfname:
                self.nn[r] = True
            return Val(r, t)
        if name in self.assigned and name not in self.gdecl:
            self.err(f"local variable '{name}' is read before its first assignment")
        if name in self.gtypes:
            t = self.gtypes[name]
            return Val(self.ins(f"load {lt(t)}, ptr @g.{name}"), t)
        if name == "__name__":
            return Val(self.sconst("__main__"), "str")
        if name in self.aliases:
            return self.modattr(self.aliases[name])
        if name in self.funcs:
            self.err(f"function '{name}' cannot be used as a value")
        self.err(f"name '{name}' is not defined")
        return Val("", "")

    def declare(self, name: str, t: str) -> None:
        if self.is_global(name):
            if name not in self.gtypes:
                self.gtypes[name] = t
                self.globs.append(f"@g.{name} = internal global {lt(t)} zeroinitializer")
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
        else:
            if name not in self.ltype:
                self.alloca(v.t, name)
            t = self.ltype[name]
            self.emit(f"store {lt(t)} {self.coerce(v, t).v}, ptr {self.lreg[name]}")

    def names_in(self, t: Node, out: list[str]) -> None:
        if t.kind == "name":
            out.append(t.s)
        elif t.kind == "tuple":
            for k in t.kids:
                self.names_in(k, out)

    def collect(self, body: list[Node]) -> None:
        # Python's rule: a name assigned anywhere in a function is local to it
        for st in body:
            k = st.kind
            if k == "assign" or k == "annassign" or k == "augassign" or k == "for":
                names: list[str] = []
                for i in range(len(st.kids) - 1 if k == "assign" else 1):
                    self.names_in(st.kids[i], names)
                for nm in names:
                    self.assigned[nm] = True
            for kid in st.kids:
                if kid.kind == "block":
                    self.collect(kid.kids)

    def target_type(self, n: Node) -> str:
        # expected type of an assignment target (types empty [] / {} literals)
        if n.kind == "name":
            return self.ltype.get(n.s, self.gtypes.get(n.s, "") if self.is_global(n.s) else "")
        if (n.kind == "attr" or n.kind == "index") and n.kids[0].kind == "name":
            o = n.kids[0].s
            t = self.ltype.get(o, self.gtypes.get(o, ""))
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
            p = self.field(self.expr(t.kids[0], ""), t.s)
            self.emit(f"store {lt(p.t)} {self.coerce(v, p.t).v}, ptr {p.v}")
        elif k == "index":
            o = self.expr(t.kids[0], "")
            if is_list(o.t):
                ix = self.coerce(self.expr(t.kids[1], "int"), "int")
                s = self.to_slot(self.coerce(v, elem(o.t)))
                self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {ix.v}", f"i64 {s}"])
            elif is_dict(o.t):
                kv = targs(o.t)
                key = self.to_slot(self.coerce(self.expr(t.kids[1], kv[0]), kv[0]))
                self.rt("pys_dict_set", "void", [f"ptr {o.v}", f"i64 {key}", "i64 " + self.to_slot(self.coerce(v, kv[1]))])
            else:
                self.err(f"'{o.t}' does not support item assignment")
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
        self.n = 0
        self.cur = "entry"
        self.term = False
        self.ret = f.ret
        self.cold = {}
        self.nn = {}
        self.selfname = ""
        self.line = f.node.line
        if not self.modlevel:
            self.collect(body)
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
                    self.emit(f"store {lt(t)} {v.v}, ptr {self.field(me, fl).v}")
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
        for st in m.kids:
            if st.kind == "class":
                self.classes[st.s] = ClassInfo(st.s, st)
        for st in m.kids:
            if st.kind == "def":
                self.funcs[st.s] = self.declare_fn(st, "")
                top.append(mk("defaults", st.s, st.line, []))
            elif st.kind == "class":
                for d in st.kids[0].kids:
                    if d.kind == "def":
                        self.classes[st.s].methods[d.s] = self.declare_fn(d, st.s)
                top.append(mk("cdefaults", st.s, st.line, []))
            else:
                top.append(st)
        for ci in self.classes.values():
            self.declare_fields(ci)
        self.modlevel = True
        self.function(FnInfo("<module>", "@main.init", m, ""), top)
        self.modlevel = False
        for f in self.funcs.values():
            self.function(f, f.node.kids[2].kids)
        for ci in self.classes.values():
            for f in ci.methods.values():
                if f.ll not in self.lazy:
                    self.function(f, f.node.kids[2].kids)
        done: dict[str, bool] = {}
        while True:
            todo: list[FnInfo] = []
            for f in self.lazy.values():
                if f.ll in self.called and f.ll not in done:
                    todo.append(f)
            if len(todo) == 0:
                break
            for f in todo:
                done[f.ll] = True
                self.function(f, f.node.kids[2].kids)
        hdr: list[str] = ["; generated by pystachy"]
        for ci in self.classes.values():
            hdr.append(f"%C.{ci.name} = type {{{', '.join([lt(ci.ftypes[x]) for x in ci.fields])}}}")
        hdr.extend(self.globs)
        hdr.extend(self.consts)
        hdr.extend(self.out)
        hdr.extend(self.decls.values())
        hdr.append("declare void @pys_init(i32, ptr)")
        hdr.append("define i32 @main(i32 %argc, ptr %argv) {")
        hdr.append("  call void @pys_init(i32 %argc, ptr %argv)")
        hdr.append("  call void @main.init()")
        hdr.append("  ret i32 0")
        hdr.append("}")
        return "\n".join(hdr) + "\n"

    # ---- statements
    def stmts(self, body: list[Node]) -> None:
        for s in body:
            self.stmt(s)

    def hidden(self, name: str, v: Val) -> str:
        # a compiler-made global, assigned here
        self.globs.append(f"{name} = internal global {lt(v.t)} zeroinitializer")
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
        # class-body defaults are evaluated once, when the class statement runs, and shared
        for fl in ci.fields:
            if fl in ci.fdefault and not is_const(ci.fdefault[fl]) and fl not in ci.fglob:
                t = ci.ftypes[fl]
                self.line = ci.fdefault[fl].line
                if self.is_dc(ci.name) and (is_list(t) or is_dict(t) or self.is_dc(t)):
                    self.err(f"mutable default {t} for dataclass field '{fl}' is not allowed")
                ci.fglob[fl] = self.hidden(f"@d.c.{ci.name}.{fl}", self.coerce(self.expr(ci.fdefault[fl], t), t))
        init = ci.methods["__init__"]
        for f in ci.methods.values():
            if f.name != "__init__" or init.node.kids[0].kind != "noann":
                self.hoist(f)
        if init.node.kids[0].kind == "noann":
            for j in range(1, len(init.params)):
                init.dglob[j] = ci.fglob.get(init.params[j], "")

    def loop(self, body: list[Node], cont: str, brk: str) -> None:
        self.loops.append(cont)
        self.loops.append(brk)
        self.stmts(body)
        self.loops.pop()
        self.loops.pop()

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
            if len(n.kids) == 2 and t0.kind == "tuple" and val.kind == "tuple" and len(t0.kids) == len(val.kids):
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
            self.for_(n)
        elif k == "return":
            if self.modlevel:
                self.err("'return' outside function")
            if len(n.kids) == 0 or (self.ret == "None" and n.kids[0].kind == "None"):
                if self.ret != "None":
                    self.err(f"missing return value of type {self.ret}")
                self.emit("ret void")
            else:
                if self.ret == "None":
                    self.err("returning a value from a function without a return annotation")
                v = self.coerce(self.expr(n.kids[0], self.ret), self.ret)
                self.emit(f"ret {lt(self.ret)} {v.v}")
            self.term = True
        elif k == "break" or k == "continue":
            if len(self.loops) == 0:
                self.err(f"'{k}' outside loop")
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
            name = "Exception"
            msg = self.sconst("")
            if len(n.kids) > 0:
                e = n.kids[0]
                if e.kind == "call" and e.kids[0].kind == "name":
                    name = e.kids[0].s
                    if len(e.kids) > 1:
                        msg = self.to_str(self.expr(e.kids[1], "")).v
                elif e.kind == "name":
                    name = e.s
                else:
                    self.err("unsupported raise statement")
            self.raise_(name, msg)
        elif k == "del":
            dt = n.kids[0]
            o = self.expr(dt.kids[0], "") if dt.kind == "index" else Val("", "")
            if is_list(o.t):
                self.rt("pys_list_pop", "i64", [f"ptr {o.v}", f"i64 {self.coerce(self.expr(dt.kids[1], 'int'), 'int').v}"])
            elif is_dict(o.t):
                kt = targs(o.t)[0]
                self.rt("pys_dict_pop", "i64", [f"ptr {o.v}", "i64 " + self.to_slot(self.coerce(self.expr(dt.kids[1], kt), kt))])
            else:
                self.err("only 'del list[i]' and 'del dict[key]' are supported")
        elif k == "lcappend":
            et = self.lct[-1]
            v = self.expr(n.kids[0], et)
            if et == "":
                self.lct[-1] = v.t
                et = v.t
            self.rt("pys_list_append", "void", [f"ptr {self.lcs[-1]}", "i64 " + self.to_slot(self.coerce(v, et))])
        elif k == "defaults":
            self.hoist(self.funcs[n.s])
        elif k == "cdefaults":
            self.hoist_class(self.classes[n.s])
        elif k == "import":
            for a in n.kids:
                mod = a.kids[1].s
                if mod not in MODULES:
                    self.err(f"module '{mod}' is not supported (available: {', '.join(MODULES.keys())})")
                if mod == "dataclasses" and a.kids[0].s != "dataclasses" and a.kids[0].s != "dataclasses.dataclass":
                    self.err(f"{a.kids[0].s} is not supported")
                self.aliases[a.s] = a.kids[0].s
        elif k == "def" or k == "class":
            self.err("nested functions and classes are not supported")
        elif k != "pass":
            self.err(f"unsupported statement '{k}'")

    def augassign(self, n: Node) -> None:
        t = n.kids[0]
        op = n.s
        if t.kind == "name":
            cur = self.load_name(t.s)
            if is_list(cur.t) and op == "+":
                self.rt("pys_list_extend", "void", [f"ptr {cur.v}", f"ptr {self.coerce(self.expr(n.kids[1], cur.t), cur.t).v}"])
            else:
                self.store_name(t.s, self.arith(op, cur, self.expr(n.kids[1], cur.t)))
        elif t.kind == "attr":
            p = self.field(self.expr(t.kids[0], ""), t.s)
            cur = Val(self.ins(f"load {lt(p.t)}, ptr {p.v}"), p.t)
            if is_list(cur.t) and op == "+":
                self.rt("pys_list_extend", "void", [f"ptr {cur.v}", f"ptr {self.coerce(self.expr(n.kids[1], cur.t), cur.t).v}"])
            else:
                r = self.coerce(self.arith(op, cur, self.expr(n.kids[1], cur.t)), p.t)
                self.emit(f"store {lt(p.t)} {r.v}, ptr {p.v}")
        elif t.kind == "index":
            o = self.expr(t.kids[0], "")
            if is_list(o.t):
                et = elem(o.t)
                i = self.coerce(self.expr(t.kids[1], "int"), "int")
                cur = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"]), et)
                r = self.coerce(self.arith(op, cur, self.expr(n.kids[1], et)), et)
                self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {i.v}", "i64 " + self.to_slot(r)])
            elif is_dict(o.t):
                kv = targs(o.t)
                key = self.to_slot(self.coerce(self.expr(t.kids[1], kv[0]), kv[0]))
                cur = self.from_slot(self.rt("pys_dict_getitem", "i64", [f"ptr {o.v}", f"i64 {key}"]), kv[1])
                r = self.coerce(self.arith(op, cur, self.expr(n.kids[1], kv[1])), kv[1])
                self.rt("pys_dict_set", "void", [f"ptr {o.v}", f"i64 {key}", "i64 " + self.to_slot(r)])
            else:
                self.err(f"'{o.t}' does not support item assignment")
        else:
            self.err("invalid target for augmented assignment")

    def for_(self, n: Node) -> None:
        tgt = n.kids[0]
        it = n.kids[1]
        body = n.kids[2].kids
        if it.kind == "call" and it.kids[0].kind == "name" and it.kids[0].s not in self.ltype:
            fn = it.kids[0].s
            args = it.kids[1:]
            if fn == "range":
                vs = self.range_args(args)
                self.for_range(tgt, vs[0], vs[1], vs[2], body)
                return
            if ((fn == "enumerate" or fn == "reversed") and len(args) == 1) or (fn == "zip" and len(args) > 1):
                self.for_seq(tgt, [self.expr(a, "") for a in args], fn, body)
                return
        if it.kind == "call" and len(it.kids) == 1 and it.kids[0].kind == "attr":
            m = it.kids[0].s
            if m == "items" or m == "keys" or m == "values":
                o = self.expr(it.kids[0].kids[0], "")
                if is_dict(o.t):
                    self.for_seq(tgt, [o], m, body)
                else:
                    self.for_seq(tgt, [self.method(o, m, [])], "", body)
                return
        self.for_seq(tgt, [self.expr(it, "")], "", body)

    def range_args(self, args: list[Node]) -> list[str]:
        vs: list[str] = []
        for a in args:
            vs.append(self.coerce(self.expr(a, "int"), "int").v)
        if len(vs) == 1:
            vs.insert(0, "0")
        if len(vs) == 2:
            vs.append("1")
        if len(vs) != 3:
            self.err("range() takes 1 to 3 arguments")
        return vs

    def for_range(self, tgt: Node, start: str, stop: str, step: str, body: list[Node]) -> None:
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

    def for_seq(self, tgt: Node, seqs: list[Val], mode: str, body: list[Node]) -> None:
        # one indexed loop serves lists, strings, dicts, enumerate, zip and reversed
        ctr = self.alloca("int", "")
        self.emit(f"store i64 0, ptr {ctr}")
        lc = self.label()
        lb = self.label()
        ls = self.label()
        le = self.label()
        self.place(lc)
        i = self.ins(f"load i64, ptr {ctr}")
        size = ""
        for s in seqs:
            if not (s.t == "str" or is_list(s.t) or is_dict(s.t)):
                self.err(f"cannot iterate over {s.t}")
            k = self.ins(f"load i64, ptr {s.v}")
            size = k if size == "" else self.ins(f"select i1 {self.ins(f'icmp slt i64 {k}, {size}')}, i64 {k}, i64 {size}")
        self.cbr(self.ins(f"icmp slt i64 {i}, {size}"), lb, le)
        self.place(lb)
        j = self.ins(f"sub i64 {self.ins(f'sub i64 {size}, 1')}, {i}") if mode == "reversed" else i
        vals: list[Val] = []
        if mode == "enumerate":
            vals.append(Val(i, "int"))
        for s in seqs:
            if is_list(s.t):
                vals.append(self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {s.v}", f"i64 {j}"]), elem(s.t)))
            elif s.t == "str":
                vals.append(Val(self.rt("pys_str_get", "ptr", [f"ptr {s.v}", f"i64 {j}"]), "str"))
            else:
                kv = targs(s.t)
                if mode != "values":
                    vals.append(self.from_slot(self.rt("pys_dict_key", "i64", [f"ptr {s.v}", f"i64 {j}"]), kv[0]))
                if mode == "values" or mode == "items":
                    vals.append(self.from_slot(self.rt("pys_dict_val", "i64", [f"ptr {s.v}", f"i64 {j}"]), kv[1]))
        if len(vals) == 1:
            self.assign(tgt, vals[0])
        elif tgt.kind == "tuple" and len(tgt.kids) == len(vals):
            for k2 in range(len(vals)):
                self.assign(tgt.kids[k2], vals[k2])
        else:
            self.assign(tgt, self.tuple_(vals))
        self.loop(body, ls, le)
        self.place(ls)
        nx = self.ins(f"add i64 {i}, 1")
        self.emit(f"store i64 {nx}, ptr {ctr}")
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
                r = self.ins(f"icmp ne i64 {self.coerce(self.call_fn(ms['__len__'], [Val(v.v, t)], []), 'int').v}, 0")
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
            return self.load_name(n.s)
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
            if path != "":
                return self.modattr(path)
            p = self.field(self.expr(n.kids[0], ""), n.s)
            return Val(self.ins(f"load {lt(p.t)}, ptr {p.v}"), p.t)
        if k == "index":
            return self.index(n)
        if k == "slice":
            o = self.expr(n.kids[0], "")
            bnd: list[str] = []
            for x in n.kids[1:]:
                bnd.append("-9223372036854775808" if x.kind == "omit" else self.coerce(self.expr(x, "int"), "int").v)
            if o.t != "str" and not is_list(o.t):
                self.err(f"'{o.t}' cannot be sliced")
            fn = "pys_str_slice" if o.t == "str" else "pys_list_slice"
            return Val(self.rt(fn, "ptr", [f"ptr {o.v}", f"i64 {bnd[0]}", f"i64 {bnd[1]}"]), o.t)
        if k == "list":
            et = elem(want) if is_list(want) else ""
            items: list[Val] = []
            for e in n.kids:
                v = self.expr(e, et)
                if et == "":
                    et = v.t
                items.append(self.coerce(v, et))
            if et == "" or et == "None":
                self.err("cannot infer the type of an empty list; add a type annotation")
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
                if kv[1] == "":
                    kv[1] = b.t
                ks.append(self.coerce(a, kv[0]))
                vs.append(self.coerce(b, kv[1]))
            if kv[0] == "":
                self.err("cannot infer the type of an empty dict; add a type annotation")
            if kv[0] != "int" and kv[0] != "str":
                self.err("dict keys must be int or str")
            r = self.rt("pys_dict_new", "ptr", [f"i64 {1 if kv[0] == 'str' else 0}"])
            for i in range(len(ks)):
                self.rt("pys_dict_set", "void", [f"ptr {r}", "i64 " + self.to_slot(ks[i]), "i64 " + self.to_slot(vs[i])])
            return Val(r, f"dict[{kv[0]},{kv[1]}]")
        if k == "tuple":
            ws = targs(want) if is_tuple(want) else []
            vals: list[Val] = []
            for i in range(len(n.kids)):
                vals.append(self.expr(n.kids[i], ws[i] if i < len(ws) else ""))
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
                    v = self.expr(part.kids[0], "")
                    d = self.sconst(self.desc(v.t))
                    s = Val(self.rt("pys_format", "ptr", ["i64 " + self.to_slot(v), f"ptr {d}", f"ptr {self.sconst(part.s)}"]), "str")
                else:
                    s = self.to_str(self.expr(part, ""))
                acc = s if i == 0 else Val(self.rt("pys_str_add", "ptr", [f"ptr {acc.v}", f"ptr {s.v}"]), "str")
            return acc
        self.err(f"unsupported expression '{k}'")
        return Val("", "")

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
            i = self.coerce(self.expr(n.kids[1], "int"), "int")
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

    def listcomp(self, n: Node, want: str) -> Val:
        # [e for t in it if c] runs as a loop appending to a fresh list; t is scoped to it
        res = self.rt("pys_list_new", "ptr", ["i64 0"])
        names: list[str] = []
        self.names_in(n.kids[1], names)
        saved: list[str] = []
        for nm in names:
            saved.append(self.ltype.get(nm, "") + " " + self.lreg.get(nm, ""))
            if nm in self.ltype:
                del self.ltype[nm]
            self.compvars[nm] = self.compvars.get(nm, 0) + 1
        app = mk("lcappend", "", n.line, [n.kids[0]])
        body = [app]
        if len(n.kids) == 4:
            body = [mk("if", "", n.line, [n.kids[3], mk("block", "", n.line, [app]), mk("block", "", n.line, [])])]
        self.lcs.append(res)
        self.lct.append(elem(want) if is_list(want) else "")
        self.for_(mk("for", "", n.line, [n.kids[1], n.kids[2], mk("block", "", n.line, body)]))
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

    def dunder(self, op: str, a: Val, b: Val) -> Val:
        # operator overloading, resolved statically: a + b -> A.__add__(a, b)
        m = DUNDER.get(op, "")
        if a.t not in self.classes:
            return Val("", "")
        ms = self.classes[a.t].methods
        if m in ms and (op == "==" or op == "!="):
            return self.eqcall(ms[m], op == "==", a, b)
        if m in ms:
            if op in ICMP:
                self.notnone(a, f"TypeError: '{op}' not supported between instances of 'NoneType' and '{tname(b.t)}'")
            else:
                self.notnone(a, f"TypeError: unsupported operand type(s) for {op}: 'NoneType' and '{tname(b.t)}'")
            return self.call_fn(ms[m], [a, b], [])
        if op == "!=" and "__eq__" in ms:
            return Val(self.ins(f"xor i1 {self.dunder('==', a, b).v}, true"), "bool")
        return Val("", "")

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

    def arith(self, op: str, a: Val, b: Val) -> Val:
        du = self.dunder(op, a, b)
        if du.t != "":
            return du
        if a.t == "bool" and b.t == "bool" and (op == "&" or op == "|" or op == "^"):
            return Val(self.ins(f"{IOPS[op]} i1 {a.v}, {b.v}"), "bool")
        a = self.as_int(a)
        b = self.as_int(b)
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
            b = self.expr(n.kids[1], "")
            return self.cmp2(ops[0], self.expr(n.kids[0], b.t), b)
        a = self.expr(n.kids[0], "")
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
            acc = "false"
            for i in range(len(targs(b.t))):
                acc = self.ins(f"or i1 {acc}, {self.cmp2('==', a, self.tget(b, i)).v}")
            return Val(acc if op == "in" else self.ins(f"xor i1 {acc}, true"), "bool")
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
            return Val(self.ins(f"fcmp {FCMP[op]} double {self.as_float(a).v}, {self.as_float(b).v}"), "bool")
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
            r = self.rt("pys_cmp", "i64", [f"i64 {sa}", f"i64 {sb}", d])
            return Val(self.ins(f"icmp {ICMP[op]} i64 {r}, 0"), "bool")
        self.err(f"cannot compare {a.t} {op} {b.t}")
        return a

    # ---- calls
    def call(self, n: Node, want: str) -> Val:
        f = n.kids[0]
        args = n.kids[1:]
        if f.kind == "name" and f.s not in self.ltype:
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
            if path != "":
                return self.builtin(path, args, want)
            return self.method(self.expr(f.kids[0], ""), f.s, args)
        self.err("only functions, classes and methods can be called")
        return Val("", "")

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
            return Val("", "None")
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
        if path == "math.pi":
            return Val(fbits("3.141592653589793"), "float")
        if path == "math.e":
            return Val(fbits("2.718281828459045"), "float")
        if path == "math.inf":
            return Val(fbits("inf"), "float")
        self.err(f"unsupported module attribute {path}")
        return Val("", "")

    def builtin(self, name: str, args: list[Node], want: str) -> Val:
        # builtins and module functions ("os.system"); most are one call listed in CALLS
        if name == "print":
            return self.print_(args)
        for a in args:
            if a.kind == "kw" and name != "open":
                self.err(f"{name}() does not accept keyword arguments")
        if name == "list" and len(args) == 1 and args[0].kind == "call" and args[0].kids[0].kind == "name" and args[0].kids[0].s == "range":
            vs = self.range_args(args[0].kids[1:])
            return Val(self.rt("pys_range_list", "ptr", [f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"]), "list[int]")
        if len(args) == 0 and name in DEFAULTS:
            args = [self.parse_expr(DEFAULTS[name])]
        w = want if name == "list" or name == "sorted" or name == "dict" else ""
        vals = [self.expr(a, w) for a in args if a.kind != "kw"]
        key = f"{name}({','.join([v.t for v in vals])})"
        if key in DEFAULTS:
            vals.append(self.expr(self.parse_expr(DEFAULTS[key]), ""))
            key = f"{name}({','.join([v.t for v in vals])})"
        if key not in CALLS and name.startswith("math."):
            vals = [self.as_float(v) for v in vals]
            key = f"{name}({','.join([v.t for v in vals])})"
        if key in CALLS:
            spec = CALLS[key].split(":")
            r = spec[1] if spec[1] != "" else vals[0].t
            return self.rres(self.rt(spec[0], rtt(r), [self.rarg(v) for v in vals]), r)
        if len(vals) == 0:
            self.err(f"unsupported call {name}()")
        v = vals[0]
        if v.t == "str" and len(vals) == 1 and (name == "sorted" or name == "min" or name == "max"):
            v = Val(self.rt("pys_str_list", "ptr", [f"ptr {v.v}"]), "list[str]")
        t = v.t
        if name == "len":
            if t in self.classes and "__len__" in self.classes[t].methods:
                self.notnone(v, "TypeError: object of type 'NoneType' has no len()")
                return self.call_fn(self.classes[t].methods["__len__"], [v], [])
            if t == "str" or is_list(t) or is_dict(t):
                return Val(self.ins(f"load i64, ptr {v.v}"), "int")
            if is_tuple(t):
                return Val(str(len(targs(t))), "int")
        elif name == "str":
            return self.to_str(v)
        elif name == "repr":
            return self.repr(v)
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
        elif name == "min" or name == "max":
            for b in vals[1:]:
                b = self.coerce(b, t)
                gt = self.cmp2(">" if name == "max" else "<", b, v)
                v = Val(self.ins(f"select i1 {gt.v}, {lt(t)} {b.v}, {lt(t)} {v.v}"), t)
            return v
        elif (name == "sorted" or name == "list") and is_list(t):
            c = self.rt("pys_list_copy", "ptr", [f"ptr {v.v}"])
            if name == "sorted":
                self.rt("pys_list_sort", "void", [f"ptr {c}", f"ptr {self.sconst(self.desc(elem(t)))}"])
            return Val(c, t)
        elif name == "list" and is_dict(t):
            return Val(self.rt("pys_dict_keys", "ptr", [f"ptr {v.v}"]), f"list[{targs(t)[0]}]")
        elif name == "range" or name == "enumerate" or name == "zip" or name == "reversed":
            self.err(f"{name}() is only supported directly in a for loop")
        if name in self.gtypes or name in self.ltype:
            self.err(f"'{name}' is not callable")
        self.err(f"unsupported call {key}")
        return v

    def parse_expr(self, text: str) -> Node:
        return Parser(Lexer(text, self.line).run()).test()

    def print_(self, args: list[Node]) -> Val:
        sep = self.sconst(" ")
        end = self.sconst("\n")
        fd = "1"
        vals: list[Val] = []
        for a in args:
            if a.kind != "kw":
                vals.append(self.expr(a, ""))
            elif a.s == "sep" or a.s == "end":
                s = self.coerce(self.expr(a.kids[0], "str"), "str").v
                if a.s == "sep":
                    sep = s
                else:
                    end = s
            elif a.s == "file":
                p = self.dotted(a.kids[0])
                if p != "sys.stdout" and p != "sys.stderr":
                    self.err("print(file=...) supports only sys.stdout and sys.stderr")
                fd = "2" if p == "sys.stderr" else "1"
            elif a.s != "flush":
                self.err(f"print() got an unexpected keyword argument '{a.s}'")
        parts = [self.to_str(v).v for v in vals]
        for i in range(len(parts)):
            if i > 0:
                self.rt("pys_write", "void", [f"ptr {sep}", f"i64 {fd}"])
            self.rt("pys_write", "void", [f"ptr {parts[i]}", f"i64 {fd}"])
        self.rt("pys_write", "void", [f"ptr {end}", f"i64 {fd}"])
        return Val("", "None")

    def bmethod(self, o: Val, m: str, args: list[Node]) -> Val:
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
                v = self.coerce(self.expr(args[i], pt), pt)
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
        if m not in ms:
            self.err(f"cannot convert {v.t} to str; define __repr__")
        if v.v in self.nn:
            return self.call_fn(ms[m], [v], [])
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(self.ins(f"icmp eq ptr {v.v}, null"), l1, l2)
        self.place(l1)
        self.br(l3)
        self.place(l2)
        r = self.call_fn(ms[m], [v], [])
        e2 = self.cur
        self.br(l3)
        self.place(l3)
        return Val(self.ins(f"phi ptr [{self.sconst('None')}, %{l1}], [{r.v}, %{e2}]"), "str")

    def repr(self, v: Val) -> Val:
        if v.t in self.classes:
            return self.obj_str(v, "__repr__")
        if "O" in self.desc(v.t) or v.t == "file" or v.t == "None":
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
    if cmd == "ir" and out == "":
        print(ir, end="")
        return
    tmp = out if cmd == "ir" else f"/tmp/pystachy{os.getpid()}.ll"
    f = open(tmp, "w", encoding="latin-1")
    f.write(ir)
    f.close()
    if cmd == "ir":
        return
    home = os.getenv("PYSTACHY_HOME", "")
    if home == "":
        s = argv[0].rfind("/")
        home = argv[0][:s] if s >= 0 else "."
        if not os.path.exists(home + "/runtime.c"):
            home = home + "/.."
    rtc = home + "/runtime.c"
    rtb = home + "/build/runtime.bc"
    llvm = os.getenv("PYSTACHY_LLVM", "")  # optional directory holding clang, opt, lli, llvm-link, llvm-as
    if llvm != "" and not llvm.endswith("/"):
        llvm = llvm + "/"
    # strip clang's target-cpu/features attributes so LLVM can inline runtime helpers into our code
    strip = "sed -E 's/ \"(target-cpu|target-features|tune-cpu)\"=\"[^\"]*\"//g'"
    if sh(f"mkdir -p {q(home + '/build')} && (test {q(rtb)} -nt {q(rtc)} || {llvm}clang -O2 -S -emit-llvm {q(rtc)} -o - | {strip} | {llvm}llvm-as -o {q(rtb)})") != 0:
        fail("cannot build the runtime (are clang and LLVM 18 installed? see PYSTACHY_LLVM)", 0)
    bc = tmp[:-3] + ".bc"
    link = f"{llvm}llvm-link --only-needed {q(tmp)} {q(rtb)} -o {q(bc)}"
    if cmd == "build":
        # AOT tier: full -O2 over program + runtime as one module (whole-program optimization)
        if out == "":
            out = SRC[:-3] if SRC.endswith(".py") else SRC + ".exe"
        code = sh(f"{link} && {llvm}clang -O2 {q(bc)} -o {q(out)} -lm")
    else:
        # JIT tier: cheap SSA cleanup, then LLVM's ORC JIT compiles for the host CPU
        fast = f"{llvm}opt -passes='mem2reg,instcombine<no-verify-fixpoint>,simplifycfg'"
        code = sh(f"{link} && {fast} {q(bc)} -o {q(bc)} && {llvm}lli {q(bc)} {' '.join([q(a) for a in rest])}")
    sh(f"rm -f {q(tmp)} {q(bc)}")
    sys.exit(code)


if __name__ == "__main__":
    main()
