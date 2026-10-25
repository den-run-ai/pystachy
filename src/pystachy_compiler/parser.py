"""Parser component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import CPYSTACK, MAXNEST, TOODEEP, fail
from src.pystachy_compiler.lexer import ESCAPES, Lexer, Tok, big_key, debug_text, string_end, utf8
from src.pystachy_compiler.scope import Symtable
from src.pystachy_compiler.syntax import (
    AUGOPS,
    BINOPS,
    CMPOPS,
    LAMBDAS,
    Node,
    STARTS,
    as_target,
    bad_target,
    expr_name,
    flat_del,
    has_kind,
    mk,
    start,
)

ATOMS: list[str] = "id int float complex str fstr rfstr bytes ... None True False ) ] }".split()  # what ends an atom


def bytes_repr(b: str) -> str:
    # repr() of the bytes whose characters b holds, one per byte
    q = '"' if "'" in b and '"' not in b else "'"
    out: list[str] = []
    for c in b:
        o = ord(c)
        if c == q or c == "\\":
            out.append("\\" + c)
        elif c == "\t" or c == "\n" or c == "\r":
            out.append("\\t" if c == "\t" else "\\n" if c == "\n" else "\\r")
        elif o < 32 or o >= 127:
            out.append("\\x" + "0123456789abcdef"[o >> 4] + "0123456789abcdef"[o & 15])
        else:
            out.append(c)
    return "b" + q + "".join(out) + q


def int_digits(r: float) -> str:
    # the digits of the int that float r equals ("" if none: it is not integral, or inf), past what
    # 64 bits hold too: r halved to fit, then the digits doubled back
    if r - r != 0.0 or (abs(r) < 9.2e18 and r != float(int(r))):
        return ""
    v = abs(r)
    n = 0
    while v >= 9.2e18:
        v = v / 2
        n += 1
    d = str(int(v))
    for _ in range(n):
        out: list[str] = []
        carry = 0
        for i in range(len(d) - 1, -1, -1):
            x = (ord(d[i]) - 48) * 2 + carry
            out.append(chr(48 + x % 10))
            carry = x // 10
        if carry > 0:
            out.append(chr(48 + carry))
        out.reverse()
        d = "".join(out)
    return ("-" if r < 0 and d != "0" else "") + d


class Parser:
    def __init__(self, toks: list[Tok]):
        self.exact_ints = False  # opted-in integer frontend, including nested f-strings
        self.toks = toks
        self.p = 0
        self.early = True  # only a docstring and from __future__ imports so far
        self.loops = 0  # loops around the statement being parsed, in its function or class
        self.infn = False  # inside a def
        self.nest = 0  # the parser's own recursion: nested expressions and elif branches
        self.blocks = 0  # the blocks around the statement being parsed (0: a module's top level)
        self.extra = 0  # CPython's parser's levels other than those: in brackets, blocks and operators
        self.xstar = -1  # the loops around the except* block the statement is in (-1: none)
        self.errs: list[str] = ["", "", ""]  # see later()
        self.at: list[int] = [0, 0, 0]
        # an f-string field's parser: the parsers it is in, and where each is, whose tokens follow
        self.outer: list[list[Tok]] = []
        self.outerp: list[int] = []
        self.fend = -1  # (in a field's parser: where its expression ends, see fail())
        self.cutmsg = ""  # the tokenizer's error that cut short the f-string being parsed (see field())
        self.cutline = 0
        self.incut = ""  # that error, in any parser of a field of that f-string (or see limit())
        self.incutline = 0
        self.probe = 0  # (reading an f-string after an expression, see reads(): the line of its error)
        self.fnl: list[int] = []  # where the newlines are in the text of the f-string being parsed
        self.undecoded: list[Node] = []  # the f-string's literal text, until it ends (see flush())
        self.pieces: list[list[str]] = []
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
        if self.probe > 0:
            return  # (CPython's parser reads an f-string there without its rules for errors)
        if self.fend < 0:
            self.reads()
        a = self.toks[self.orp]
        e = self.orn
        k = self.peek()
        if k == "-" or k == "+" or k == "~" or k == "not":
            k = self.ahead()
        if (k not in STARTS and k != "id") or k == "yield":
            return
        b = self.toks[self.orp + 1].kind
        named = a.kind == "id" and (b == "str" or b == "fstr" or b == "rfstr" or b == "bytes")
        if self.fend >= 0:
            # (in an f-string field, CPython's parser reads the expression after it as far as it
            # goes, and after a name's strings the one after those: a tokenizer error there, or
            # where a field cut short ends, comes first)
            r = self.reach(self.p)
            if named and self.toks[r].kind in STARTS:
                r = self.reach(r)
            if self.toks[r].kind == "error" or self.toks[r].kind == "stop":
                fail(self.toks[r].text, self.toks[r].line)
            if self.cutmsg != "" and r >= self.fend:
                fail(self.cutmsg, self.cutline)
        if e.kind == "name" and (e.s == "print" or e.s == "exec"):
            self.fail(f"Missing parentheses in call to '{e.s}'. Did you mean {e.s}(...)?", e.line)
        if named or (a.kind == "id" and (a.text == "match" or a.text == "case" or a.text == "_" or a.text == "type")):
            return
        self.fail("invalid syntax. Perhaps you forgot a comma?", start(e))

    def reach(self, i: int) -> int:
        # the token where CPython's parser stops reading the expression that starts at token i:
        # one that cannot continue it, or a tokenizer error
        operand = True  # (where an operand is expected)
        depth = 0
        while True:
            k = self.toks[i].kind
            if k == "error" or k == "stop" or k == "?" or k == "eof":
                return i
            opening = k == "(" or k == "[" or k == "{"
            closing = k == ")" or k == "]" or k == "}"
            binop = k in CMPOPS or k == "**" or k == "." or k == "if" or k == "else" or k == "and" or k == "or" or k == "is" or k == "not"
            for ops in BINOPS:
                binop = binop or k in ops
            if depth > 0 or (opening and (operand or k != "{")):
                depth += 1 if opening else (-1 if closing else 0)
                operand = False
            elif operand and k in ATOMS and not closing:
                operand = False
            elif operand and (k == "-" or k == "+" or k == "~" or k == "not" or k == "await" or k == "*"):
                pass
            elif not operand and binop:
                operand = True
            else:
                return i
            i += 1

    def reads(self) -> None:
        # where CPython's parser fails right after an expression, its rule for a missing comma
        # (invalid_expression) reads the expression that follows, without its rules for errors:
        # strings there that end with an f-string cut short (see Lexer.string) end with the
        # tokenizer's error that cut it, unless an error in a field comes first, which is then
        # "invalid syntax" (but for an error of CPython's actions, see fail())
        j = self.p
        while self.toks[j].kind == "str" or self.toks[j].kind == "fstr" or self.toks[j].kind == "rfstr" or self.toks[j].kind == "bytes":
            if self.toks[j].part:
                self.probe = self.toks[self.p].line
                self.incut = self.toks[j + 1].text
                self.incutline = self.toks[j + 1].line
                self.atom()  # (which fails)
            j += 1

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
        # only if it opened on a line before the one the parser got to, outside an f-string.
        # (At the end of a field cut short, CPython's parser meets the tokenizer's error first.)
        if self.cutmsg != "" and self.fend >= 0 and self.p >= self.fend:
            fail(self.cutmsg, self.cutline)
        if self.probe > 0 and not (msg.startswith("(unicode error)") or msg.startswith("f-string: invalid conversion character '") or msg.startswith("f-string: conversion type")):
            fail("invalid syntax", self.probe)  # (see reads(); CPython's actions raise theirs)
        if msg == "invalid syntax" and self.fend < 0 and self.ore == self.p:
            self.reads()
        if msg == "invalid syntax" and self.fend >= 0:
            # in an f-string field's expression, CPython's parser expects '=', '!', ':' or '}'
            # after the longest expression it can read from the field's start (if any: one ends
            # with an atom outside brackets, but not with a lambda's parameter)
            msg = "f-string: expecting a valid expression after '{'"
            line = self.toks[1].line
            depth = 0
            for k in range(1, min(self.p, self.fend)):
                t = self.toks[k]
                depth += 1 if t.kind == "(" or t.kind == "[" or t.kind == "{" else 0
                depth -= 1 if t.kind == ")" or t.kind == "]" or t.kind == "}" else 0
                if depth == 0 and t.kind == "lambda":
                    break
                if depth == 0 and (t.kind in ATOMS or (k == 1 and t.kind == "yield")):
                    msg = "f-string: expecting '=', or '!', or ':', or '}'"
                    line = self.toks[k + 1].line  # (at the token after it)
            if self.toks[1].kind == "=":
                msg = "f-string: valid expression required before '='"
        cur = max(self.toks[min(self.p, len(self.toks) - 1)].line, line)
        # (in an f-string field, those after the outermost f-string: CPython's tokenizer errors in
        # an f-string replace no parser error)
        toks = self.toks if len(self.outer) == 0 else self.outer[0]
        for t in toks[self.p if len(self.outer) == 0 else self.outerp[0] :]:
            if t.kind == "error" or (t.kind == "stop" and not t.part and t.text.endswith("was never closed") and t.line < cur):
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
        return mk("block", "doc" if doc else "", 1, body)  # (with its docstring: Loader.docstring())

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
        self.blocks += 1
        if self.eat("nl"):
            self.expect("indent")
            while not self.eat("dedent"):
                if not self.eat("nl"):
                    self.stmt(body)
        else:
            self.simple(body)
        self.blocks -= 1
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
                tpk: list[str] = []
                self.typeparams(tps, line, tpk)
                # class C[T, *Ts]: a generic class; a kid per type parameter tells its kind (s: "",
                # "*" for a TypeVarTuple or "**" for a ParamSpec, then "=" for a default)
                bases.append(mk("typeparams", " ".join(tps), line, [mk("str", x, line, []) for x in tpk]))
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
            # per case a "pattern" node (s: the names the pattern's captures bind; kids: the guard,
            # then the names, dotted names and f-strings that the pattern reads) and the block
            self.p += 1
            n = mk("match", "", line, [self.exprlist(True)])
            if n.kids[0].kind == "starred":
                self.invalid(self.line())  # (a starred subject needs a comma: match *a, b:)
            self.expect(":")
            self.expect("nl")
            self.expect("indent")
            trees: list[Node] = []
            guards: list[bool] = []
            while not self.eat("dedent"):
                if self.eat("nl"):
                    continue
                if self.toks[self.p].text != "case":
                    self.fail("expected 'case'", self.line())
                pat = mk("pattern", "", self.line(), [])
                self.p += 1
                tree = self.patterns()
                guards.append(self.eat("if"))
                if guards[-1]:
                    pat.kids.append(self.named())
                self.expect(":")
                caps: list[str] = []
                self.pnames(tree, caps, pat.kids)
                pat.s = " ".join(caps)
                trees.append(tree)
                n.kids.append(pat)
                n.kids.append(self.block())
            # CPython's compiler checks each case's pattern in turn: one that cannot fail must be last
            # or have a guard (and a last case _ is not compiled as a pattern)
            last = len(trees) - 1
            wild = last > 0 and trees[last].kind == "pas" and trees[last].s == "" and len(trees[last].kids) == 0
            for i in range(last if wild else last + 1):
                if self.pcheck(trees[i], guards[i] or i == last, []):
                    break
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

    # ---- a case's patterns, parsed as CPython's grammar has them, into nodes of their own: "pas" (a
    # capture, the wildcard _ or p as name: s the name, "" for _; kids p), "pvalue" (a literal or a
    # dotted name), "pconst" (None, True or False: s), "pseq", "pstar" (*name or *_: s), "pmap" (kids
    # each key, then its pattern; s **name), "pclass" (kids the class, its positional patterns,
    # then "pkw" ones: s the attribute) and "por" (kids the alternatives). A number literal is a
    # "pnum": s its value's repr(), kids its "num" nodes (see number_repr), the first's s a key that
    # equal numbers share ("" for a complex number whose real part no float holds)
    def patterns(self) -> Node:
        # a case's patterns: a pattern, or an open sequence of them (a, *b)
        line = self.line()
        p = self.pstarred()
        if self.peek() != ",":
            if p.kind == "pstar":
                self.invalid(self.line())
            return p
        kids = [p]
        while self.eat(","):
            if self.peek() == ":" or self.peek() == "if":
                break
            kids.append(self.pstarred())
        return mk("pseq", "", line, kids)

    def pstarred(self) -> Node:
        # a pattern, or in a sequence *name or *_
        line = self.line()
        if not self.eat("*"):
            return self.pattern()
        t = self.toks[self.p]
        if self.peek() != "id" or (t.text != "_" and (self.ahead() == "." or self.ahead() == "(" or self.ahead() == "=")):
            self.invalid(t.line)
        self.p += 1
        return mk("pstar", "" if t.text == "_" else t.text, line, [])

    def pattern(self) -> Node:
        # alternatives (a | b), maybe bound as a name (... as x)
        line = self.line()
        p = self.pclosed()
        if self.peek() == "|":
            p = mk("por", "", line, [p])
            while self.eat("|"):
                p.kids.append(self.pclosed())
        if not self.eat("as"):
            return p
        t = self.toks[self.p]
        if self.peek() == "id" and t.text == "_":
            self.fail("cannot use '_' as a target", t.line)
        if t.kind == "id" and self.ahead() != "." and self.ahead() != "(" and self.ahead() != "=":
            self.p += 1
            return mk("pas", t.text, line, [p])
        if t.kind != "id" and t.kind in STARTS:
            self.test()  # (an expression other than a name)
            self.fail("invalid pattern target", t.line)
        self.invalid(t.line)
        return p

    def pclosed(self) -> Node:
        # a literal, a capture, _, a dotted name's value, (pattern), or a sequence, mapping or class pattern
        self.deeper()
        k = self.peek()
        t = self.toks[self.p]
        line = t.line
        p = mk("pseq", "", line, [])
        if k == "int" or k == "float" or k == "complex" or k == "-" or k == "str" or k == "fstr" or k == "rfstr" or k == "bytes":
            p = mk("pvalue", "", line, [self.pliteral()])
        elif k == "None" or k == "True" or k == "False":
            self.p += 1
            p = mk("pconst", k, line, [])
        elif k == "id" and (t.text == "_" or (self.ahead() != "." and self.ahead() != "(" and self.ahead() != "=")):
            self.p += 1
            p = mk("pas", "" if t.text == "_" else t.text, line, [])
        elif k == "id":
            e = self.pdotted()
            if self.eat("("):
                p = self.pclass(e, line)
            elif e.kind == "attr" and self.peek() != "=":
                p = mk("pvalue", "", line, [e])
            else:
                self.invalid(self.line())
        elif k == "(" or k == "[":
            self.p += 1
            end = ")" if k == "(" else "]"
            while not self.eat(end):
                p.kids.append(self.pstarred())
                if not self.eat(","):
                    if k == "(" and len(p.kids) == 1:
                        if p.kids[0].kind == "pstar":
                            self.invalid(self.line())
                        p = p.kids[0]  # ((pattern): the pattern)
                    self.expect(end)
                    break
        elif k == "{":
            p = self.pmapping()
        else:
            self.invalid(line)
        self.nest -= 1
        return p

    def pdotted(self) -> Node:
        # a name, or a dotted one
        t = self.toks[self.p]
        self.p += 1
        e = mk("name", t.text, t.line, [])
        while self.peek() == ".":
            line = self.line()
            self.p += 1
            e = mk("attr", self.expect("id").text, line, [e])
        return e

    def pliteral(self) -> Node:
        # a string, or a number: maybe negated, or a real one + or - an imaginary one
        k = self.peek()
        if k == "str" or k == "fstr" or k == "rfstr" or k == "bytes":
            j = self.p
            while self.toks[j].kind == "str" or self.toks[j].kind == "fstr" or self.toks[j].kind == "rfstr" or self.toks[j].kind == "bytes":
                if self.toks[j].kind != "str" and self.toks[j].kind != "bytes":
                    return mk("fstr", "", self.line(), [self.atom()])  # (no constant, even without fields)
                j += 1
            return self.atom()
        line = self.line()
        neg = self.eat("-")
        t = self.toks[self.p]
        if self.peek() != "int" and t.kind != "float" and t.kind != "complex":
            self.invalid(t.line)
        self.p += 1
        re = mk("num", ("-" if neg else "") + t.text, line, [])
        if t.big != "":
            # (a literal too big for 64 bits, written in base 16, 8 or 2: keys compare its value)
            re.s = ("-" if neg else "") + big_key(t.big)
        if self.peek() != "+" and self.peek() != "-":
            return mk("pnum", self.number_repr(re, mk("num", "", line, [])), line, [re])
        if t.kind == "complex":
            self.fail("real number required in complex literal", t.line)
        sign = self.toks[self.p].kind
        self.p += 1
        u = self.toks[self.p]
        if self.peek() != "int" and u.kind != "float" and u.kind != "complex":
            self.invalid(u.line)
        if u.kind != "complex":
            self.fail("imaginary number required in complex literal", u.line)
        self.p += 1
        im = mk("num", sign + u.text, line, [])
        return mk("pnum", self.number_repr(re, im), line, [re, im])

    def number_repr(self, re: Node, im: Node) -> str:
        # repr() of the number literal re, or of the complex number re + im (re - im): both texts as
        # the lexer gives them, maybe negated (and im "" for none); re.s becomes the value's
        # floats ("real imag"), or an int's digits, which key equality compares ("" for a real part
        # that is an int no float holds, which CPython cannot add to an imaginary number)
        x = re.s[1:] if re.s.startswith("-") else re.s
        isint = x.startswith("0x") or (not x.endswith("j") and "." not in x and "e" not in x and "E" not in x)
        if isint and im.s == "":
            # an int: its digits (as written, but leading zeros), which may not fit in 64 bits (a
            # float equal to it has the same, see int_digits); or "0x" and its hexadecimal digits,
            # past 14,285 bits (big_key)
            x = x if x.startswith("0x") else x.lstrip("0")
            x = "0" if x == "" else x
            re.s = ("-" if re.s.startswith("-") and x != "0" else "") + x
            return re.s
        if isint and (x.startswith("0x") or float(x) - float(x) != 0.0):
            # (CPython's compiler leaves the sum or difference an expression, which pcheck rejects)
            re.s = ""
            return ""
        r = 0.0
        i = 0.0
        if x.endswith("j"):
            i = -float(x[:-1]) if re.s.startswith("-") else float(x[:-1])
            r = -0.0 if re.s.startswith("-") else 0.0  # (-1j is complex(-0.0, -1.0))
        else:
            r = -float(x) if re.s.startswith("-") else float(x)
        if im.s != "":
            # real + imaginary: CPython adds them as complex numbers, (r + 0.0, 0.0 + i)
            v = float(im.s[1:-1])
            r = r + 0.0 if im.s.startswith("+") else r - 0.0
            i = 0.0 + v if im.s.startswith("+") else 0.0 - v
        if not x.endswith("j") and im.s == "":
            # a float: equal to the int it holds, as a key
            re.s = int_digits(r) if int_digits(r) != "" else repr(r) + " 0.0"
            return repr(r)
        re.s = int_digits(r) if i == 0.0 and int_digits(r) != "" else repr(r + 0.0) + " " + repr(i + 0.0)
        ri = repr(i)
        ri = ri[:-2] if ri.endswith(".0") else ri
        if r == 0.0 and not repr(r).startswith("-"):
            return ri + "j"
        rr = repr(r)
        return "(" + (rr[:-2] if rr.endswith(".0") else rr) + ("" if ri.startswith("-") else "+") + ri + "j)"

    def pclass(self, cls: Node, line: int) -> Node:
        # Class(positional patterns, attribute=pattern ...) after its '('
        p = mk("pclass", "", line, [cls])
        kw = False
        while not self.eat(")"):
            t = self.toks[self.p]
            if t.kind == "id" and self.ahead() == "=":
                self.p += 2
                p.kids.append(mk("pkw", t.text, t.line, [self.pattern()]))
                kw = True
            else:
                q = self.pattern()
                if kw:
                    self.fail("positional patterns follow keyword patterns", q.line)
                p.kids.append(q)
            if not self.eat(","):
                self.expect(")")
                break
        return p

    def pmapping(self) -> Node:
        # {key: pattern, ..., **name}: a key is a literal, None, True, False or a dotted name
        p = mk("pmap", "", self.line(), [])
        self.p += 1
        while not self.eat("}"):
            if self.eat("**"):
                t = self.toks[self.p]
                if self.peek() != "id" or t.text == "_" or self.ahead() == "." or self.ahead() == "(" or self.ahead() == "=":
                    self.invalid(t.line)
                self.p += 1
                p.s = t.text
                self.eat(",")
                self.expect("}")
                break
            k = self.peek()
            if k == "None" or k == "True" or k == "False":
                p.kids.append(mk(k, "", self.line(), []))
                self.p += 1
            elif k == "id":
                e = self.pdotted()
                if e.kind != "attr":
                    self.invalid(self.line())
                p.kids.append(e)
            else:
                p.kids.append(self.pliteral())
            self.expect(":")
            p.kids.append(self.pattern())
            if not self.eat(","):
                self.expect("}")
                break
        return p

    def pnames(self, p: Node, caps: list[str], reads: list[Node]) -> None:
        # the names that pattern p's captures bind, in order, and the names, dotted names and f-strings
        # it reads (a value, a class, a key)
        k = p.kind
        if k == "pvalue" or k == "pclass":
            if p.kids[0].kind == "name" or p.kids[0].kind == "attr" or p.kids[0].kind == "fstr":
                reads.append(p.kids[0])
            for q in p.kids[1:]:
                self.pnames(q.kids[0] if q.kind == "pkw" else q, caps, reads)
        elif k == "pmap":
            for i in range(0, len(p.kids), 2):
                if p.kids[i].kind == "attr" or p.kids[i].kind == "fstr":
                    reads.append(p.kids[i])
                self.pnames(p.kids[i + 1], caps, reads)
        else:
            for q in p.kids:
                self.pnames(q, caps, reads)
        if (k == "pas" or k == "pstar" or k == "pmap") and p.s != "":
            caps.append(p.s)

    def pcheck(self, p: Node, irrefutable: bool, stores: list[str]) -> bool:
        # CPython's compiler, compiling pattern p (compiler_pattern), where p may be a capture or _
        # (irrefutable) and the names in stores are bound already: the first error it reports there
        # (later(); then True)
        k = p.kind
        if k == "pas" and len(p.kids) == 0 and not irrefutable:
            self.later(2, f"name capture '{p.s}' makes remaining patterns unreachable" if p.s != "" else "wildcard makes remaining patterns unreachable", p.line)
            return True
        if k == "pas" or k == "pstar":
            return (len(p.kids) > 0 and self.pcheck(p.kids[0], irrefutable, stores)) or self.pstore(p.s, p.line, stores)
        if k == "pvalue" and (p.kids[0].kind == "fstr" or (p.kids[0].kind == "pnum" and p.kids[0].kids[0].s == "")):
            self.later(2, "patterns may only match literals and attribute lookups", p.line)
            return True
        if k == "pseq":
            star = False
            for q in p.kids:
                if q.kind == "pstar" and star:
                    self.later(2, "multiple starred names in sequence pattern", p.line)
                    return True
                star = star or q.kind == "pstar"
        if k == "pmap":
            seen: list[str] = []
            for i in range(0, len(p.kids), 2):
                key = p.kids[i]
                if key.kind == "fstr" or (key.kind == "pnum" and key.kids[0].s == ""):
                    self.later(2, "mapping pattern keys may only match literals and attribute lookups", p.line)
                    return True
                if key.kind != "attr":
                    # a constant: equal keys are an error (1, 1.0 and True; but no other str
                    # equals a str, no other bytes a bytes)
                    v = key.kids[0].s if key.kind == "pnum" else ("1" if key.kind == "True" else "0" if key.kind == "False" else key.kind + ":" + key.s)
                    if v in seen:
                        r = key.s if key.kind == "pnum" else repr(key.s) if key.kind == "str" else bytes_repr(key.s) if key.kind == "bytes" else key.kind
                        self.later(2, f"mapping pattern checks duplicate key ({r})", p.line)
                        return True
                    seen.append(v)
            for i in range(1, len(p.kids), 2):
                if self.pcheck(p.kids[i], True, stores):
                    return True
            return self.pstore(p.s, p.line, stores)
        if k == "pclass":
            kws = [q for q in p.kids if q.kind == "pkw"]
            for i in range(len(kws)):
                if kws[i].s == "__debug__":
                    self.later(2, "cannot assign to __debug__", kws[i].kids[0].line)
                    return True
                for j in range(i + 1, len(kws)):
                    if kws[j].s == kws[i].s:
                        self.later(2, f"attribute name repeated in class pattern: {kws[i].s}", kws[j].kids[0].line)
                        return True
            for q in p.kids[1:]:
                if self.pcheck(q.kids[0] if q.kind == "pkw" else q, True, stores):
                    return True
            return False
        if k == "por":
            # each alternative but the last must be able to fail, and all bind the same names
            control: list[str] = []
            for i in range(len(p.kids)):
                alt: list[str] = []
                if self.pcheck(p.kids[i], irrefutable and i == len(p.kids) - 1, alt):
                    return True
                if i == 0:
                    control = alt
                elif len(alt) != len(control) or len([nm for nm in control if nm not in alt]) > 0:
                    self.later(2, "alternative patterns bind different names", p.line)
                    return True
            for nm in control:
                if nm in stores:
                    self.later(2, f"multiple assignments to name '{nm}' in pattern", p.line)
                    return True
                stores.append(nm)
            return False
        for q in p.kids if k == "pseq" else p.kids[:0]:
            if self.pcheck(q, True, stores):
                return True
        return False

    def pstore(self, name: str, line: int, stores: list[str]) -> bool:
        # a pattern binds name ("" for none): CPython's compiler checks that nothing else in it does
        if name == "__debug__":
            self.later(2, "cannot assign to __debug__", line)
            return True
        if name != "" and name in stores:
            self.later(2, f"multiple assignments to name '{name}' in pattern", line)
            return True
        if name != "":
            stores.append(name)
        return False

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
            self.typeparams(tps, line, [])
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
            if self.tp_mentions(p.kids[0], tps):
                self.dropped(line, mk("annotation", "", line, [p.kids[0]]))
                p.kids[0] = mk("noann", " ".join(tps), line, [p.kids[0]])
        if self.tp_mentions(ret, tps):
            self.dropped(line, mk("annotation", "", line, [ret]))
            ret = mk("noann", " ".join(tps), line, [ret])
        body = self.scope(True)
        body.s = " ".join(tps)  # (which name type variables of their own in it: Loader.qstmts)
        return mk("def", name, line, [params, ret, body])

    def tp_mentions(self, a: Node, tps: list[str]) -> bool:
        # (funcdef) does annotation a mention one of type parameters tps, also in a string, a
        # forward reference (-> "Box[U]"), as Loader.qann parses it
        if a.kind == "str" and len(tps) > 0:
            return self.tp_mentions(Parser(Lexer(a.s, a.line).run()).test(), tps)
        if a.kind == "name":
            return a.s in tps
        for k in a.kids:
            if self.tp_mentions(k, tps):
                return True
        return False

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

    def typeparams(self, out: list[str], line: int, kinds: list[str]) -> None:
        # [T, U: bound, *Ts, **P, V = default] after the name of a def, a class or a type alias (on
        # line): their names, and in kinds "", "*" or "**" for each, with "=" after it if it has a
        # default
        if self.toks[self.p + 1].kind == "]":
            self.fail("Type parameter list cannot be empty", self.line())
        self.expect("[")
        defaults = False  # (whether a parameter so far has a default)
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
            if name == "__classdict__":  # (CPython's symbol table, which keeps the name for class scopes)
                self.later(0, "reserved name '__classdict__' cannot be used for type parameter", at)
            self.no_debug(name, at)
            out.append(name)
            kinds.append("**" if kind == "ParamSpec" else "*" if kind == "TypeVarTuple" else "")
            colon = self.line()
            if self.eat(":"):
                b = self.test()
                if kind != "TypeVar":  # (CPython's grammar: only a TypeVar has a bound or constraints)
                    self.fail(f"cannot use {'constraints' if b.kind == 'tuple' else 'bound'} with {kind}", colon)
                self.scoped(b, "a TypeVar constraint" if b.kind == "tuple" else "a TypeVar bound")
                self.dropped(line, b)
            if self.eat("="):
                b = self.item() if kind == "TypeVarTuple" else self.test()  # (CPython's grammar: a star expression only for a TypeVarTuple)
                self.scoped(b, f"a {kind} default")
                self.dropped(line, b)
                kinds[len(kinds) - 1] = kinds[len(kinds) - 1] + "="
                defaults = True
            elif defaults:  # (CPython's compiler, compiling the type parameters)
                self.later(2, f"non-default type parameter '{name}' follows default type parameter", at)
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
        if (k == "listcomp" or k == "asynccomp" or k == "setcomp" or k == "dictcomp") and has_kind(e, "walrus"):
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
            # type X[T] = value (PEP 695): s is X; at a module's top level, its kid is a
            # "typeparams" node (s: the type parameters; kids: the value, then their kinds as a
            # class's), which the loader makes a type alias (Loader.bindings)
            self.p += 1
            name = self.expect("id").text
            tps: list[str] = []
            tpk: list[str] = []
            if self.peek() == "[":
                self.typeparams(tps, line, tpk)
            self.expect("=")
            v = self.test()
            self.scoped(v, "a type alias")
            self.dropped(line, v)
            self.no_debug(name, line)
            if self.blocks > 0:
                return mk("typealias", name, line, [])
            return mk("typealias", name, line, [mk("typeparams", " ".join(tps), line, [v] + [mk("str", x, line, []) for x in tpk])])
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
                if path == "_collections_abc":
                    # import collections.abc as _collections_abc (CPython's collections binds
                    # sys.modules['collections.abc'] to this module: one module, of two names)
                    path = "collections.abc"
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
            x = "*" if not paren and len(n.kids) == 0 and self.eat("*") else self.expect("id").text  # (a * alone, unparenthesized)
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
        if path == "_collections_abc" and n.s == "from":
            # from collections.abc import ... (the same module, as for import _collections_abc)
            for a in n.kids:
                a.kids[0].s = "collections.abc" + a.kids[0].s[16:]
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
            # has a default, then "#" and a number that tells it from the other lambdas of its line)
            ps = self.params(":", line)
            self.deeper()  # (a lambda counts as two levels, as a ** does)
            b = self.test()
            self.nest -= 1
            LAMBDAS[0] += 1
            return mk("lambda", ("=" if len([x for x in ps.kids if x.kids[1].kind != "noann"]) > 0 else "") + f"#{LAMBDAS[0]}", line, [ps, b])
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
        # [e for t in it if c]; with more for and if clauses (or with async for, an "asynccomp"
        # node), the clauses after the first iterable are "compif" (kids: the condition) and
        # "compfor" (the target, the iterable) nodes; s is "async" for an async for clause (the
        # first: of the node itself, until a generator expression's is "gen")
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
        if len(n.kids) == 4 and len(ts) == 1 and not aio:
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
            return mk(k, "0" + t.big if self.exact_ints and t.big != "" else t.text, line, [])
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
            # CPython decodes each in turn (before it reads the next token), then checks that all
            # or none are bytes.
            n = mk("fstr", "", line, [])
            nb = 0
            parts = 0
            bs: list[str] = []  # (the bytes of each bytes literal, a character per byte)
            pt = t
            while True:
                parts += 1
                if pt.kind == "bytes":
                    self.bytes_check(pt)
                    bs.append(self.bytes_unescape(pt.text) if pt.esc else pt.text)
                    nb += 1
                elif pt.kind == "str":
                    n.kids.append(mk("str", self.unescape(pt.text, pt.line) if pt.esc else pt.text, pt.line, []))
                else:
                    saved = self.cutmsg
                    savedline = self.cutline
                    if pt.part:
                        self.cutmsg = self.toks[self.p].text  # (the error after it)
                        self.cutline = self.toks[self.p].line
                        self.incut = self.cutmsg
                        self.incutline = self.cutline
                    self.fnl = []
                    nl = pt.text.find("\n")
                    while nl >= 0:
                        self.fnl.append(nl)
                        nl = pt.text.find("\n", nl + 1)
                    self.undecoded = []
                    self.pieces = []
                    self.fparts(pt.text, 0, pt.kind == "rfstr", pt.line, n, 0)
                    if not pt.part:
                        # (CPython decodes an f-string's literal text once it has read its end)
                        for ui in range(len(self.undecoded)):
                            self.undecoded[ui].s = "".join([self.unescape(x, pt.line) for x in self.pieces[ui]])
                    self.cutmsg = saved
                    self.cutline = savedline
                k = self.peek()
                if k != "str" and k != "fstr" and k != "rfstr" and k != "bytes":
                    break
                pt = self.toks[self.p]
                self.p += 1
            if nb > 0 and nb < parts:
                self.fail("cannot mix bytes and nonbytes literals", self.line())
            if nb > 0:
                return mk("bytes", "".join(bs), line, [])
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
                    d.kind = "dictstar"
                    d.kids.append(mk("dstar", "", at, [self.binary(0)]))  # (keys and values stay pairs)
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
                    if d.kind == "dictstar" and seen > 1:
                        self.invalid(at)
                    if d.kind == "dictstar":
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
        if self.fend >= 0:
            self.p -= 1  # (in an f-string field, fail() reads the tokens before this one)
        self.invalid(line)
        return mk("omit", "", line, [])

    def fparts(self, s: str, i: int, raw: bool, line: int, n: Node, spec: int) -> int:
        # the parts of an f-string body from s[i] (or of a format spec: spec 1, or 2 after a field
        # in it), appended to n: literal text as str nodes, each replacement field as fmt(expression,
        # spec). A format spec ends at its field's '}', whose index is returned (len(s) if none).
        # Lexer.fstring() read the f-string as CPython's tokenizer does (line: its first line)
        text: list[str] = []  # the literal text so far, in the pieces CPython decodes: to each doubled brace
        lit: list[str] = []  # (and the rest)
        while i < len(s):
            c = s[i]
            if c == "}" and spec > 0:
                break
            if (c == "{" and s[i + 1 : i + 2] == "{" and spec != 1) or (c == "}" and s[i + 1 : i + 2] == "}"):
                lit.append(c)
                text.append("".join(lit))
                lit = []
                i += 2
            elif c == "}":
                fail("f-string: single '}' is not allowed", self.fline(line, i))
            elif c == "{":
                self.flush(text + ["".join(lit)], raw, line, n, spec)
                text = []
                lit = []
                i = self.field(s, i + 1, raw, line, n)
                spec = 2 if spec > 0 else 0
            elif c == "\\" and s[i + 1 : i + 2] != "{" and s[i + 1 : i + 2] != "}":
                # an escaped character; a \N{...} escape is one, whose '}' closes no field
                k = i + 2
                if not raw and s[i + 1 : i + 3] == "N{":
                    k = s.find("}", i) + 1 if s.find("}", i) >= 0 else len(s)
                lit.append(s[i : max(k, i + 2)])
                i = max(k, i + 2)
            else:
                lit.append(c)
                i += 1
        self.flush(text + ["".join(lit)], raw, line, n, spec)
        return i

    def field(self, s: str, i: int, raw: bool, line: int, n: Node) -> int:
        # the replacement field whose expression starts at s[i], appended to n (after its text, if
        # it is self-documenting); returns the index past its '}'. The expression ends at a
        # top-level '}', ':' or '!' (but not '!='); its text leaves out the comments in it, which
        # run to the end of their line
        j = i
        depth = 0
        code: list[str] = []
        while j < len(s) and (depth > 0 or not (s[j] == "}" or s[j] == ":" or (s[j] == "!" and s[j + 1 : j + 2] != "="))):
            k = j + 1
            if s[j] == "'" or s[j] == '"':
                k = string_end(s, j)
            elif s[j] == "#":
                k = s.find("\n", j)
                j = len(s) if k < 0 else k
                continue
            elif s[j] == "(" or s[j] == "[" or s[j] == "{":
                depth += 1
            elif s[j] == ")" or s[j] == "]" or s[j] == "}":
                depth -= 1
            code.append(s[j:k])
            j = k
        at = self.fline(line, j)  # (the line of s[j])
        ran = j >= len(s)  # (to the end of an f-string cut short, see cut())
        text = "".join(code)
        src = text.rstrip()
        while src.endswith("\\"):
            src = src[:-1].rstrip()  # (a line continuation)
        selfdoc = src.endswith("=") and not (src.endswith("==") or src.endswith("!=") or src.endswith("<=") or src.endswith(">="))
        if selfdoc:
            # f"{x=}" prints the expression's text, then its value
            n.kids.append(mk("str", debug_text(s[i:j]), line, []))
            src = src[:-1]
        # (the line of the expression's first token: a comment holds no newline)
        eline = self.fline(line, i) + text[: len(text) - len(text.lstrip())].count("\n")
        if src.strip() == "" and ran and not selfdoc:
            self.cut("f-string: expecting '}'", at)
        if src.strip() == "":
            self.fail("f-string: valid expression required before '" + ("=" if selfdoc else s[j]) + "'", eline if selfdoc else at)
        lam = src.strip()
        if lam.startswith("lambda") and not (lam[6:7].isalnum() or lam[6:7] == "_") and s[j : j + 1] == ":":
            self.fail("f-string: lambda expressions are not allowed without parentheses", eline)
        # (in parentheses, an expression may continue over lines: f"""{x\n + 1}"""); an error at
        # the closing parenthesis is on the field's last line, after which CPython's parser
        # expects '=', '!', ':' or '}' (see fail())
        lx = Lexer("(" + src.strip() + "\n)", eline)
        toks = lx.run()
        last = eline + src.strip().count("\n")
        cut = -1
        for k in range(len(toks)):
            toks[k].line = min(toks[k].line, last)
            if toks[k].kind == "stop" and toks[k].text == "non-ASCII identifiers are not supported" and self.incut != "":
                toks[k].text = self.incut  # (see limit())
                toks[k].line = self.incutline
            elif toks[k].kind == "stop" and toks[k].text == "non-ASCII identifiers are not supported":
                # (a Pystachy limitation: CPython reads on and decodes the f-string's text once it
                # ends, so an escape error in the text before the field comes first)
                for ui in range(len(self.undecoded)):
                    for x in self.pieces[ui]:
                        self.unescape(x, line)
            if (toks[k].kind == "error" or toks[k].kind == "stop") and ran and self.cutmsg != "" and lx.halt >= len(lx.src) - 1:
                # a bracket left open in a field cut short: where it ends (instead of the
                # parenthesis added), CPython's parser meets the error that cut it
                toks[k].kind = "stop"
                toks[k].text = self.cutmsg
                toks[k].line = self.cutline
                cut = k
        if cut > 0 and toks[cut - 1].kind == ")":
            toks = toks[: cut - 1] + toks[cut:]
        sub = Parser(toks)
        sub.exact_ints = self.exact_ints
        sub.nest = self.nest
        sub.extra = self.extra + 32  # (33 levels in CPython's parser, one of them the deeper() of the expression)
        sub.outer = self.outer + [self.toks]
        sub.outerp = self.outerp + [self.p]
        sub.fend = len(toks) - 3
        if ran and not selfdoc:
            sub.cutmsg = self.cutmsg  # (where the expression ends, CPython's parser meets the error)
            sub.cutline = self.cutline
        sub.incut = self.incut
        sub.incutline = self.incutline
        sub.probe = self.probe
        sub.expect("(")
        e = sub.no_star(sub.rhs())
        if sub.peek() == "=" and sub.toks[sub.p + 1].kind == "error":
            sub.p += 1  # (CPython's parser reads the token after it: a tokenizer error there comes first)
        if sub.peek() == "=":
            sub.fail("f-string: expecting '!', or ':', or '}'", sub.line())
        if sub.peek() != ")" and sub.ore == sub.p:
            sub.comma()
        if sub.peek() != ")":
            sub.fail("f-string: expecting '=', or '!', or ':', or '}'", sub.line())
        for cat in [0, 2]:
            if sub.errs[cat] != "":
                self.later(cat, sub.errs[cat], sub.at[cat])
        if ran:
            self.cut("f-string: expecting '}'", at)
        conv = ""
        convmsg = ""  # (an invalid conversion character's error)
        if s[j] == "!":
            # !r, !s or !a, right after the '!'; then (white space and) ':' or '}'
            k = self.fskip(s, j + 1)
            m = k
            while m < len(s) and ((s[m].isalnum() and ord(s[m]) < 128) or s[m] == "_"):
                m += 1
            conv = s[k:m]
            at = self.fline(line, k)
            if k >= len(s):
                self.cut("f-string: missing conversion character", at)
            if conv == "" and (s[k : k + 1] == ":" or s[k : k + 1] == "}"):
                self.fail("f-string: missing conversion character", at)
            if conv == "" or (conv[0] >= "0" and conv[0] <= "9"):
                self.fail("f-string: invalid conversion character", at)
            if k > j + 1:
                self.fail("f-string: conversion type must come right after the exclamation mark", self.fline(line, j))
            if conv != "r" and conv != "s" and conv != "a":
                convmsg = f"f-string: invalid conversion character '{conv}': expected 's', 'r', or 'a'"
            j = self.fskip(s, m)
            if j >= len(s):
                self.cut("f-string: expecting ':' or '}'", self.fline(line, j))
            if s[j] != ":" and s[j] != "}":
                t = Lexer(s[j:], self.fline(line, j)).run()[0]
                if t.kind == "error":
                    fail(t.text, t.line)  # (CPython's parser reads that token: a tokenizer error comes first)
                self.fail("f-string: expecting ':' or '}'", self.fline(line, j))
        spec = mk("str", "", line, [])
        colon = j < len(s) and s[j] == ":"
        if colon:
            # the spec runs to the field's '}' and may hold fields: {x:>{w}}
            sp = mk("fstr", "", line, [])
            incut = self.incut
            incutline = self.incutline
            if convmsg != "" and (incut == "" or self.spec_end(s, j + 1, raw) < len(s)):
                # (CPython parses the spec first, see limit(), and checks the character once its
                # field ends, before it meets an error that cut the f-string short after it)
                self.incut = convmsg
                self.incutline = at
            j = self.fparts(s, j + 1, raw, line, sp, 1)
            self.incut = incut
            self.incutline = incutline
            if j >= len(s):
                self.cut("f-string: expecting '}', or format specs", self.fline(line, j))
            plain = True
            for kd in sp.kids:
                if kd.kind != "str":
                    plain = False
            spec = sp if not plain else mk("str", "".join([kd.s for kd in sp.kids]), line, [])
        if j >= len(s) or s[j] != "}":
            self.fail("f-string: expecting '}'", self.fline(line, j))
        if convmsg != "":
            self.fail(convmsg, at)  # (CPython checks it once it has parsed the whole field)
        if selfdoc and conv == "" and not colon:
            conv = "r"
        if e.kind == "dict" and len(e.kids) == 0 and (conv != "" or (spec.kind == "str" and spec.s == "")):
            # an empty dict display (whose type Pystachy does not infer) as the text that str(),
            # repr(), ascii() and format() with an empty spec give: f"{x:{{}}}" opens such a field
            e = mk("str", "{}", line, [])
            conv = ""
        if conv != "":
            fn = "__pys_repr" if conv == "r" else ("__pys_str" if conv == "s" else "__pys_ascii")
            e = mk("call", "", line, [mk("name", fn, line, []), e])
        n.kids.append(mk("fmt", "", line, [e, spec]))
        return j + 1

    def spec_end(self, s: str, i: int, raw: bool) -> int:
        # the index of the '}' that ends the format spec from s[i] (len(s) if the text ends first:
        # in an f-string cut short, where the tokenizer's error cut it), as fparts() reads it
        after = False  # (after a field in it, '{{' is a brace)
        while i < len(s) and s[i] != "}":
            if s[i] == "{" and s[i + 1 : i + 2] == "{" and after:
                i += 2
            elif s[i] == "{":
                # a field (see field()): its expression, conversion character and spec
                i += 1
                depth = 0
                while i < len(s) and (depth > 0 or not (s[i] == "}" or s[i] == ":" or (s[i] == "!" and s[i + 1 : i + 2] != "="))):
                    if s[i] == "'" or s[i] == '"':
                        i = string_end(s, i)
                    elif s[i] == "#":
                        k = s.find("\n", i)
                        i = len(s) if k < 0 else k
                    else:
                        depth += 1 if s[i] == "(" or s[i] == "[" or s[i] == "{" else 0
                        depth -= 1 if s[i] == ")" or s[i] == "]" or s[i] == "}" else 0
                        i += 1
                while i < len(s) and s[i] != ":" and s[i] != "}":
                    i += 1  # (past its conversion character)
                if i < len(s) and s[i] == ":":
                    i = self.spec_end(s, i + 1, raw)
                i += 1
                after = True
            elif s[i] == "\\" and s[i + 1 : i + 2] != "{" and s[i + 1 : i + 2] != "}":
                # an escaped character, or a \N{...} escape, whose '}' closes no field
                k = s.find("}", i) if not raw and s[i + 1 : i + 3] == "N{" else i + 1
                i = len(s) if k < 0 else k + 1
            else:
                i += 1
        return min(i, len(s))

    def fline(self, line: int, i: int) -> int:
        # the line of character i of the f-string being parsed, whose first line is line
        lo = 0
        hi = len(self.fnl)
        while lo < hi:
            m = (lo + hi) // 2
            if self.fnl[m] < i:
                lo = m + 1
            else:
                hi = m
        return line + lo

    def limit(self, msg: str, line: int) -> None:
        # a Pystachy limitation; in an f-string cut short, CPython reads on to the tokenizer's
        # error that cut it (unless an error in a field comes first), and in the spec of a field
        # with an invalid conversion character to the end of the field and that error
        if self.incut != "":
            fail(self.incut, self.incutline)
        self.fail(msg, line)

    def cut(self, msg: str, line: int) -> None:
        # an error where an f-string's text ends, after the tokenizer's error that cut it short
        # (see Lexer.string), if any
        if self.cutmsg != "":
            fail(self.cutmsg, self.cutline)
        self.fail(msg, line)

    def fskip(self, s: str, j: int) -> int:
        # past the white space and comments from s[j] in a replacement field
        while j < len(s) and (s[j] == " " or s[j] == "\t" or s[j] == "\n" or s[j] == "\r" or s[j] == "\f" or s[j] == "#"):
            if s[j] == "#":
                k = s.find("\n", j)
                j = len(s) if k < 0 else k
            else:
                j += 1
        return j

    def flush(self, text: list[str], raw: bool, line: int, n: Node, spec: int) -> None:
        # an f-string's literal text, in the pieces CPython decodes (see fparts): at once in a format
        # spec, and in its body once the f-string ends (see atom)
        t = mk("str", "".join(text), line, [])
        if t.s == "":
            return
        if not raw and spec > 0:
            t.s = "".join([self.unescape(x, line) for x in text])
        elif not raw:
            self.undecoded.append(t)
            self.pieces.append(text)
        n.kids.append(t)

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
                self.limit("\\N{...} escapes are not supported", line)
            elif e == "\n":
                pass
            elif e in ESCAPES:
                out.append(ESCAPES[e])
            else:
                out.append("\\" + e)
            at += i - b
        return "".join(out)

    def bytes_unescape(self, s: str) -> str:
        # decode the backslash escapes of a bytes literal's source text, which bytes_check has
        # checked: a character per byte. \x, an octal escape (CPython keeps its low 8 bits, with
        # a SyntaxWarning above \377) and the named escapes give a byte; \u, \U, \N and any other
        # escape are none (their backslash stays), and a backslash ends a line in the literal
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
            if e == "x":
                out.append(chr(int(s[i : i + 2], 16)))
                i += 2
            elif e >= "0" and e <= "7":
                v = ord(e) - 48
                for _ in range(2):
                    if i < n and s[i] >= "0" and s[i] <= "7":
                        v = v * 8 + ord(s[i]) - 48
                        i += 1
                out.append(chr(v & 255))
            elif e == "\n":
                pass
            elif e in ESCAPES:
                out.append(ESCAPES[e])
            else:
                out.append("\\" + e)
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
