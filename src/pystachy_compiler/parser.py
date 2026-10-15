"""Parser component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import CPYSTACK, MAXNEST, TOODEEP, fail
from src.pystachy_compiler.lexer import ESCAPES, Lexer, Tok, utf8
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
    mentions,
    mk,
    start,
)


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
                    d.kind = "dictstar"
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
