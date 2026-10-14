"""Scope component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import scope_binds, target_names
from src.pystachy_compiler.diagnostics import LINES, fail
from src.pystachy_compiler.specs import FUTURE
from src.pystachy_compiler.syntax import Node, has_kind, start


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
