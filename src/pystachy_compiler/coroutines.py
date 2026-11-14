"""Coroutines component of the self-hosting Pystachy compiler.

An async def compiles as a generator function does (generators.py): an LLVM switched-resume
coroutine whose call makes a coroutine object, of type coro[Y,None,R], and runs none of its body.
Its awaits are its suspension points. await delegates to an awaitable as yield from delegates to a
generator (PEP 380, PEP 492): what that yields goes on to the code that runs the coroutine
(send(), throw()), what is thrown into the coroutine is thrown into it, closing the coroutine closes
it, and what it returns, read from its promise, is the await's value. The awaitables are coroutine
objects, the generators of a @types.coroutine generator function, and objects whose __await__ is a
generator method. Y, what the coroutine yields to the code that runs it, is None until an await of
something that yields another type decides it; R is its return annotation, or what its returns
return. See docs/internals.md#coroutines.
"""
from __future__ import annotations
from src.pystachy_compiler.analysis import local_names
from src.pystachy_compiler.diagnostics import int_program, shown
from src.pystachy_compiler.ir import FnInfo, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import BIG, GENCLEAN, GENDONE, GENEXC, GENSTATE, TYPESMOD
from src.pystachy_compiler.syntax import Node, has_kind, mk, names_in
from src.pystachy_compiler.utils import coro_mark, cret, cyield, fbits, gelem, gsend, is_agen, is_coro, is_gen, tname, typestr, unopt


def is_async(d: Node) -> bool:
    # is def d an async def: the parser keeps the async keyword as its first decorator, a "deco"
    # node "async" with no kids (the def's own decorators follow it)
    return len(d.kids) > 3 and d.kids[3].kind == "deco" and d.kids[3].s == "async" and len(d.kids[3].kids) == 0


def has_async(n: Node) -> bool:
    # does code n define an async def: a program that does runs its coroutines with send() and
    # throw(), so its generators keep what those need (Gen.gproto), and tells a coroutine that has
    # not started from one suspended where it awaits (GENNEW)
    if n.kind == "def" and is_async(n):
        return True
    for k in n.kids:
        if has_async(k):
            return True
    return False


def reused(t: str) -> str:
    # CPython's message for an awaitable of coroutine type t that has finished, sent or awaited
    # again: a coroutine's, or that of the awaitable of an async generator's method (coro_mark)
    m = coro_mark(t)
    return "cannot reuse already awaited " + ("__anext__()/asend()" if m == "asend" else "aclose()/athrow()" if m == "athrow" else "coroutine")


def direct_name(x: Node) -> str:
    # the name that awaited expression x calls, NAME(args) with no unpacked argument, else ""
    if x.kind != "call" or x.kids[0].kind != "name":
        return ""
    for a in x.kids[1:]:
        if a.kind == "starred" or a.kind == "dstar":
            return ""
    return x.kids[0].s


def definition_time(n: Node) -> list[Node]:
    # what the code around def or lambda n evaluates where n runs: its parameters' defaults and a
    # def's decorator expressions, not its body
    out: list[Node] = []
    for p in n.kids[0].kids:
        if len(p.kids) > 1 and p.kids[1].kind != "noann":
            out.append(p.kids[1])
    if n.kind == "def":
        for x in n.kids[3:]:
            for e in x.kids:
                out.append(e)  # (a decorator with arguments, or not a dotted name: its expression)
    return out


def desugar_async(body: list[Node], aio: bool, tmps: list[int]) -> None:
    # (Parser.module, once Symtable has checked the module) each async with and async for statement
    # of statements body, of an async def's own code (aio), becomes the statements PEP 492 gives
    # for it. Their implicit awaits are await nodes of their own kinds (s, see await_protocol), so
    # that the compiler's analyses and code see ordinary assignments, try and while statements.
    # The locals that hold the manager, the iterator and their state are named __pys_aw<k>.*, k
    # counting those of the async def (tmps): no identifier holds a dot, so no variable of the
    # program shares them, as with lower_matches' temporaries
    i = 0
    while i < len(body):
        st = body[i]
        if aio and st.kind == "async" and len(st.kids) == 1 and st.kids[0].kind == "with":
            new = st.kids[0].kids[-1].kids
            for it in reversed(st.kids[0].kids[:-1]):
                # (async with A as a, B as b: is async with A as a: async with B as b:)
                new = async_with(it, new, st.line, tmps)
            body[i : i + 1] = new
            continue  # (its block's statements are there, which may hold more)
        if aio and st.kind == "async" and len(st.kids) == 1 and st.kids[0].kind == "for":
            body[i : i + 1] = async_for(st.kids[0], st.line, tmps)
            continue
        desugar_walk(st, aio, tmps)
        i += 1


def desugar_walk(n: Node, aio: bool, tmps: list[int]) -> None:
    # the blocks of code n, whose async statements desugar_async rewrites where n is of an async
    # def's own code (aio), and its comprehensions (desugar_comp)
    if n.kind == "def":
        aio = is_async(n)
        tmps = [0]
    elif n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        aio = False
    if n.kind == "block":
        desugar_async(n.kids, aio, tmps)
        return
    if n.kind == "listcomp" or n.kind == "asynccomp":
        desugar_comp(n)
    for k in n.kids:
        desugar_walk(k, aio, tmps)


def async_first(c: Node) -> None:
    # comprehension c, which the parser makes a generator expression (its s "gen", where "async"
    # says that its first for clause is async for): that clause's iterable is marked (an "aiterof"
    # node), until desugar_comp makes it an await of kind aiterc
    if c.s == "async":
        c.kids[2] = mk("aiterof", "", c.kids[2].line, [c.kids[2]])


def desugar_comp(c: Node) -> None:
    # (desugar_walk, once Symtable has checked the module, before the comprehensions in c) the
    # iterable of each async for clause of comprehension c becomes an await node of kind aiterc:
    # what its __aiter__() gives, an async generator that a for loop over it steps through with
    # awaits (agen_aiter, for_seq). A generator expression with one, or with an await outside its
    # first iterable (which the code around it evaluates), is an asynchronous generator expression,
    # an "asynccomp" node (PEP 530: an async generator, genexp_value); any other comprehension is a
    # "listcomp", whose awaits are the function's around it (Symtable has checked that it is async)
    line = c.line
    gen = c.s == "gen"
    aio = c.kind == "asynccomp" or (gen and comp_awaits(c))
    if c.kids[2].kind == "aiterof":
        c.kids[2] = mk("await", "aiterc", line, [c.kids[2].kids[0]])
    elif c.s == "async":
        c.kids[2] = mk("await", "aiterc", line, [c.kids[2]])
        c.s = ""
    for x in c.kids[3:]:
        if x.kind == "compfor" and x.s == "async":
            x.kids[1] = mk("await", "aiterc", line, [x.kids[1]])
            x.s = ""
    c.kind = "asynccomp" if gen and aio else "listcomp"


def comp_awaits(c: Node) -> bool:
    # does generator expression c await in its own code: an await, or an asynchronous comprehension
    # inlined in it, outside its first iterable
    for k in [c.kids[0], c.kids[1]] + c.kids[3:]:
        if awaits_in(k):
            return True
    return False


def awaits_in(n: Node) -> bool:
    # does code n await (comp_awaits): outside the functions it defines (but in their defaults and
    # decorators) and the generator expressions it holds (but in their first iterables); an async
    # for clause's aiterc is no await
    if (n.kind == "await" and n.s != "aiterc") or (n.kind == "asynccomp" and n.s != "gen"):
        return True
    if n.kind == "def" or n.kind == "lambda":
        for e in definition_time(n):
            if awaits_in(e):
                return True
        return False
    if n.kind == "class" or n.kind == "subclass":
        return False
    if (n.kind == "listcomp" or n.kind == "asynccomp") and n.s == "gen":
        return awaits_in(n.kids[2])
    for k in n.kids:
        if awaits_in(k):
            return True
    return False


def async_with(it: Node, body: list[Node], line: int, tmps: list[int]) -> list[Node]:
    # async with E as T: body (item it), as PEP 492 specifies it:
    #     mgr = E; value = await (checked) mgr.__aenter__(); hit = False
    #     try: T = value; body
    #     except: hit = True; if not await mgr.__aexit__(type, value, tb): raise
    #     finally: if not hit: await mgr.__aexit__(None, None, None)
    k = str(tmps[0])
    tmps[0] += 1
    mgr = "__pys_aw" + k + ".mgr"
    hit = "__pys_aw" + k + ".hit"
    out = [mk("assign", "", line, [mk("name", mgr, line, []), it.kids[0]])]
    enter = mk("await", "aenter", line, [mk("name", mgr, line, [])])
    pre: list[Node] = []
    if len(it.kids) == 2:
        val = "__pys_aw" + k + ".val"
        out.append(mk("assign", "", line, [mk("name", val, line, []), enter]))
        pre.append(mk("assign", "", line, [it.kids[1], mk("name", val, line, [])]))
    else:
        out.append(mk("expr", "", line, [enter]))
    out.append(mk("assign", "", line, [mk("name", hit, line, []), mk("False", "", line, [])]))
    suppress = mk("unary", "not", line, [mk("await", "aexit", line, [mk("name", mgr, line, [])])])
    handler = mk("block", "", line, [mk("assign", "", line, [mk("name", hit, line, []), mk("True", "", line, [])]), mk("if", "", line, [suppress, mk("block", "", line, [mk("raise", "", line, [])]), mk("block", "", line, [])])])
    normal = mk("expr", "", line, [mk("await", "aexitnone", line, [mk("name", mgr, line, [])])])
    fin = mk("block", "finally", line, [mk("if", "", line, [mk("unary", "not", line, [mk("name", hit, line, [])]), mk("block", "", line, [normal]), mk("block", "", line, [])])])
    out.append(mk("try", "", line, [mk("block", "", line, pre + body), mk("except", "", line, [mk("omit", "", line, []), handler]), fin]))
    return out


def async_for(f: Node, line: int, tmps: list[int]) -> list[Node]:
    # async for T in E: body [else: rest] (for statement f), as PEP 492 specifies it:
    #     it = (checked) E.__aiter__(); running = True
    #     while running:
    #         try: value = await (checked) it.__anext__()
    #         except StopAsyncIteration: running = False
    #         else: T = value; body
    #     [else: rest]
    k = str(tmps[0])
    tmps[0] += 1
    it = "__pys_aw" + k + ".it"
    run = "__pys_aw" + k + ".run"
    val = "__pys_aw" + k + ".val"
    out = [mk("assign", "", line, [mk("name", it, line, []), mk("await", "aiter", line, [f.kids[1]])])]
    out.append(mk("assign", "", line, [mk("name", run, line, []), mk("True", "", line, [])]))
    step = mk("block", "", line, [mk("assign", "", line, [mk("name", val, line, []), mk("await", "anext", line, [mk("name", it, line, [])])])])
    end = mk("name", "StopAsyncIteration", line, [])
    end.made = True  # (the builtin class, whatever the program binds to its name: qexpr, catch_named)
    stop = mk("except", "", line, [end, mk("block", "", line, [mk("assign", "", line, [mk("name", run, line, []), mk("False", "", line, [])])])])
    each = mk("block", "else", line, [mk("assign", "", line, [f.kids[0], mk("name", val, line, [])])] + f.kids[2].kids)
    loop = mk("while", "", line, [mk("name", run, line, []), mk("block", "", line, [mk("try", "", line, [step, stop, each])])])
    if len(f.kids) > 3:
        loop.kids.append(f.kids[3])  # (its else block)
    out.append(loop)
    return out


def await_sites(n: Node, out: list[Node]) -> bool:
    # the awaits of code n (outside the functions, classes and lambdas it defines, but in their
    # defaults and decorators, which run here), in out; False where it also holds an asynchronous
    # comprehension, which awaits implicitly (desugar_async's implicit awaits are of a name, which
    # no async def's twin is: awaits_direct)
    if n.kind == "def" or n.kind == "lambda":
        for e in definition_time(n):
            if not await_sites(e, out):
                return False
        return True
    if n.kind == "class" or n.kind == "subclass":
        return True
    if n.kind == "async" or n.kind == "asynccomp":
        return False
    if n.kind == "await":
        out.append(n)
    for k in n.kids:
        if not await_sites(k, out):
            return False
    return True


def shadowing(n: Node, out: dict[str, bool]) -> None:
    # the names that code n binds besides its statements' targets (outside the functions,
    # classes and lambdas it defines, but in their defaults and decorators, which run here): its
    # comprehensions' targets, local to them, and the names := binds, as match captures and type
    # statements do. An await of a call of one there calls what that name holds, not a module's
    # async def
    if n.kind == "def" or n.kind == "lambda":
        for e in definition_time(n):
            shadowing(e, out)
        return
    if n.kind == "class" or n.kind == "subclass":
        return
    names: list[str] = []
    if n.kind == "listcomp" or n.kind == "asynccomp":
        names_in(n.kids[1], names)
        for k in n.kids[3:]:
            if k.kind == "compfor":
                names_in(k.kids[0], names)
    if n.kind == "walrus" or n.kind == "typealias" or n.kind == "pattern":
        names = n.s.split()
    for nm in names:
        out[nm] = True
    for k in n.kids:
        shadowing(k, out)


def gen_coro_analyze(self) -> None:
    # which async defs of the modules' top level never suspend (FnInfo.nosusp), before any code
    # compiles: those all of whose awaits are of a call, by its name, of such an async def, a name
    # that their own code does not bind. The greatest such set: async defs that await only one
    # another (a recursion) never suspend either. await of a call of one calls its twin instead
    # of making a coroutine and running it (await_value)
    cands: dict[str, FnInfo] = {}
    for name in self.funcs:
        f = self.funcs[name]
        if f.aio and not f.agen and f.bad == "" and f.cls == "" and name not in self.mvars:
            cands[name] = f
    nos: dict[str, bool] = {}
    for name in cands:
        nos[name] = True
    changed = True
    while changed:
        changed = False
        for name in cands:
            if nos[name] and not self.awaits_direct(cands[name], nos):
                nos[name] = False
                changed = True
    for name in cands:
        cands[name].nosusp = nos[name]


def gen_awaits_direct(self, f: FnInfo, nos: dict[str, bool]) -> bool:
    # is each await of async def f of a call of a name that f does not bind, the name of an async
    # def that nos holds may never suspend
    own: dict[str, bool] = {}
    local_names(f.node.kids[2].kids, own)
    shadowing(f.node.kids[2], own)
    for p in f.params:
        own[p] = True
    sites: list[Node] = []
    if not await_sites(f.node.kids[2], sites):
        return False
    for a in sites:
        name = direct_name(a.kids[0]) if a.s == "" else ""  # (an implicit await: desugar_async)
        if name == "" or name in own or name not in nos or not nos[name]:
            return False
    return True


def gen_coro_twin(self, f: FnInfo) -> FnInfo:
    # the twin of async def f, which never suspends (nosusp): the same body as an ordinary
    # function, a template of its own, whose awaits call twins too (direct), returning what f's
    # coroutine returns; a call of it is the await of a call of f (await_value)
    if f.twin is not None:
        return f.twin
    t = FnInfo(f.name, f.ll + ".sync", f.node, f.cls)
    t.params = f.params
    t.ptypes = f.ptypes
    t.defaults = f.defaults
    t.dglob = f.dglob
    t.dtypes = f.dtypes
    t.uflags = f.uflags
    t.mod = f.mod
    t.home = f.home
    t.npos = f.npos
    t.posonly = f.posonly
    t.vararg = f.vararg
    t.varelem = f.varelem
    t.kwarg = f.kwarg
    t.kwelem = f.kwelem
    t.vartup = f.vartup
    t.orig = f.orig
    t.pending = f.pending
    t.anys = f.anys
    t.pats = f.pats
    t.clo = f.clo
    t.bad = f.bad
    t.generic = True
    t.direct = True
    t.ret = f.gret
    f.twin = t
    return t


def gen_direct_await(self, x: Node) -> FnInfo | None:
    # the async def that awaited expression x calls by its name, where it never suspends (nosusp)
    # and the name is the module's: its twin runs it (await_value); else None
    name = direct_name(x)
    if name == "" or name in self.ltype or name not in self.funcs:
        return None
    f = self.funcs[name]
    if not f.aio or not f.nosusp:
        return None
    return f


def gen_coro_deco(self, x: Node, loc: dict[str, bool]) -> bool:
    # is decorator x @types.coroutine (or a name that a from import binds to it): it marks a
    # generator function whose generators await takes (FnInfo.awaitable), and changes nothing
    # else that Pystachy compiles, as CPython's sets a flag on the function's code. Not where
    # its name, or the module's (types.coroutine), is a variable of the function the def is in
    # (loc), which hides the import: that decorator is called, as any other
    if x.kind != "deco" or len(x.kids) > 0 or x.s == "async":
        return False
    if (x.s[: x.s.find(".")] if "." in x.s else x.s) in loc:
        return False
    key = self.imported(x.s) if self.imported(x.s) != "" else x.s
    return key == TYPESMOD + ".coroutine" or key == "types.coroutine"


def gen_coro_type(self, y: str, r: str) -> str:
    # the type of the coroutine objects whose awaits yield y to the code that runs them and that
    # return r: coro[Y,None,R], shown as typing's Coroutine[Y, None, R] (nothing sends them a value
    # other than None)
    return self.ctype("coro", [y, "None", r])


def gen_coro_declare(self, f: FnInfo, d: Node) -> str:
    # async def f (def d), whose own body does not yield (an async generator: gen_declare): its
    # coroutine type coro[None,None,R] (ret), R its return annotation (gret), or "" (with ret ""),
    # for its returns to decide. A template, as a generator function whose yields decide its type
    # is: its first call compiles it, so that its awaits decide Y before the code that holds its
    # coroutines does (only its own calls, compiled while it is, see the type it has then: ysure).
    # What closing it while it is suspended may run (gclose, gwith, gtry). The error where
    # Pystachy does not compile it, else ""
    f.gen = True
    f.aio = True
    body = d.kids[2].kids
    f.gwith = self.coro_scan(body, "with")
    f.gtry = False
    for st in body:
        f.gtry = f.gtry or has_kind(st, "try")
    f.gclose = has_kind(d.kids[2], "await") or f.gwith or f.gtry
    f.gsend = "None"
    f.generic = True
    if d.kids[1].kind == "noann":
        f.gret = ""
        f.gretinfer = True
        f.ret = ""
        return ""
    why = self.ann_problem(d.kids[1], True)
    if why != "":
        return why
    f.gret = self.ann(d.kids[1])
    f.gretinfer = False
    f.ret = self.coro_type("None", f.gret)
    return ""


def gen_coro_scan(self, body: list[Node], kind: str) -> bool:
    # does one of these statements await inside a statement of this kind (with)
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass" or st.kind == "lambda":
            continue
        if st.kind == kind and has_kind(st.kids[-1], "await"):
            return True
        for k in st.kids:
            if (k.kind == "block" and self.coro_scan(k.kids, kind)) or (k.kind == "except" and self.coro_scan(k.kids[1].kids, kind)):
                return True
    return False


def gen_coro_settle(self, f: FnInfo) -> None:
    # the coroutine type of async def f, being compiled, once what it returns is known: what a call
    # of it, compiled from now on, gives (an async generator's, once its first yield decides what
    # it yields: asyncgens.py)
    if f.agen:
        if f.ret != "":
            f.ret = self.agen_type(gelem(f.ret), f.gsend, f.ayield)
    elif f.gret != "":
        f.ret = self.coro_type(f.ayield, f.gret)


def gen_coro_yields(self, yi: str, callee: FnInfo | None, what: str) -> str:
    # Y of the coroutine being compiled, which awaits what, something that yields yi to the code
    # that runs it (callee: the function whose call made it, if known): None until an await of
    # something that yields another type decides it; each await's values must then be of it. An
    # await of what may yield None makes Y one that holds None (ynone). A coroutine of a recursion
    # being compiled (callee in building) whose Y is still None may yet decide it: its yields pass
    # through as they are (await_handle), and if its Y changes, the next pass compiles it with
    # that Y from the start (yield_change), where this await checks it
    f = self.curfn
    y = f.ayield
    if callee is not None and callee.ll in self.building and yi == "None":
        return y
    if yi == y:
        f.ynone = f.ynone or yi == "None"
        return y
    t = ""
    if yi == "None":
        f.ynone = True
        t = y if self.optional(y) == y else self.optional(y)
        if t == "":
            self.err(f"{short(f.name)}() yields {typestr(y)} to the code that runs it, and also awaits {what}, which may yield None: a {typestr(y)} cannot be None")
    elif y == "None":
        t = yi if not f.ynone or self.optional(yi) == yi else self.optional(yi)
        if t == "":
            self.err(f"{short(f.name)}() awaits {what}, which yields {typestr(yi)}, and an awaitable that may yield None: a {typestr(yi)} cannot be None")
    elif self.widens(yi, y) or self.optional(yi) == y:
        return y  # (Y holds what it yields: await_words converts a T into Y, T | None)
    elif self.optional(y) == yi:
        f.ynone = True  # (what yields Y | None: Y holds None now, as for an await that yields None)
        t = yi
    else:
        self.err(f"{short(f.name)}() yields {typestr(y)} to the code that runs it, but awaits {what}, which yields {typestr(yi)}")
    if t != y:
        # (the words compiled awaits yielded under the old Y are still valid where they were None's
        # zero, or a pointer that the new Y holds as it is)
        relayout = not (y == "None" or (self.none_null(y) and unopt(t) == y))
        self.yield_change(f, t, relayout, f"cannot infer what {short(f.name)}() yields to the code that runs it: code compiled before its await of {what} took it to yield {typestr(y)}, and it yields {typestr(t)}")
    return t


def gen_yield_change(self, f: FnInfo, t: str, relayout: bool, why: str) -> None:
    # Y of coroutine f, being compiled, becomes t. Where code compiled already took the old Y (a
    # call of f compiled while f is: ysure; or an await of f's that yielded words of another
    # layout: relayout), the next pass compiles f with t from the start (a "yield:" hint, Rejoin);
    # on the last pass that is an error (why)
    if f.ysure or relayout:
        if self.final or self.drying > 0:
            self.err(why)
        self.newhints["yield:" + self.fnkey(f)] = t
    f.ayield = t
    self.coro_settle(f)


def gen_ret_widen(self, f: FnInfo, t: str) -> bool:
    # async def f, being compiled, whose return type R is inferred, returns a number R and ends
    # without a value elsewhere: the next pass compiles it returning t (R | None, a box) from the
    # start (a "cret:" hint, as yield_change's, Rejoin). False on the last pass (an error then)
    if self.final or self.drying > 0:
        return False
    self.newhints["cret:" + self.fnkey(f)] = t
    return True


def gen_coro_join(self, a: str, b: str) -> str:
    # the type of the coroutines that async overrides make, which a call through their base
    # awaits, where they make coroutines of types a and b: what they yield (a None and a T: T |
    # None, as an await of both would make it) and what they return joined, else ""
    ya = cyield(a)
    yb = cyield(b)
    y = ya if ya == yb else self.join(ya, yb)
    r = self.join(cret(a), cret(b))
    return self.coro_type(y, r) if y != "" and r != "" else ""


def gen_coro_rejoin(self, f: FnInfo, base: str, t: str, vals: list[Val], insts: list[FnInfo | None]) -> None:
    # a call through base of async method f, whose overrides (each arm's call made coroutine
    # vals[i] with instance insts[i]) make coroutines of different types, joined as t
    # (coro_join): a coroutine's Y and R lay out what its frame holds, so the next pass compiles
    # each instance with t's from the start ("yield:" and "cret:" hints, as yield_change's and
    # ret_widen's); this pass goes on with t. Where a hint did not apply, or on the last pass,
    # it is an error
    why = f"overrides of {short(base)}.{f.name}() return incompatible types; use a common return type"
    for i in range(len(vals)):
        v = vals[i]
        g = insts[i]
        if v.t == t:
            continue
        if g is None or self.final:
            self.err(why)
        if self.drying == 0:
            for k in ["yield:", "cret:"]:
                h = cyield(t) if k == "yield:" else cret(t)
                if (cyield(v.t) if k == "yield:" else cret(v.t)) != h:
                    if self.hints.get(k + self.fnkey(g), "") == h:
                        self.err(why)  # (hinted already, and still another type: an annotated return)
                    self.newhints[k + self.fnkey(g)] = h
        vals[i] = Val(v.v, t)


def gen_coro_hinted(self, g: FnInfo) -> None:
    # the instance g of an async def, before it compiles: Y from an earlier pass's hint (see
    # yield_change), else None; R | None where an earlier pass found it ends without a value
    # too (ret_widen), else its annotation or what its returns decide
    h = self.hints.get("yield:" + self.fnkey(g), "")
    if h != "":
        g.ayield = h
        self.coro_settle(g)
    h = self.hints.get("cret:" + self.fnkey(g), "")
    o = self.optional(g.gret) if g.gret != "" and g.gret != "None" and not g.gretinfer else ""
    if h != "" and o != "" and o != h and self.coro_type("None", o) == self.coro_type("None", h):
        h = o  # (an annotated promoting int's int | None, whose coroutines hold the opt[int] hinted: ctype)
    if h != "" and (g.gretinfer or self.optional(g.gret) == h or (g.gret == "None" and self.optional(h) == h)):
        # (also an annotated R, where async overrides return it or None: coro_rejoin)
        g.gret = h
        self.coro_settle(g)


def gen_await_value(self, n: Node, want: str) -> Val:
    # await x (n) in the async def being compiled: x's value is an awaitable (a coroutine, a
    # @types.coroutine function's generator, or an object whose __await__ is a generator method),
    # which this coroutine runs until it returns; the value it returns is the await's (PEP 492).
    # Anything else raises CPython's TypeError here
    f = self.curfn
    if n.s == "aiterc":
        return self.agen_aiter(n.kids[0])  # (an async for clause's iterable, whose __aiter__() no await runs: desugar_comp)
    if not f.aio and not f.direct:
        self.err("'await' outside async function")
    if n.s != "":
        return self.await_protocol(n, want)  # (an implicit await of async with or async for)
    x = n.kids[0]
    g = self.direct_await(x)
    if g is not None:
        # (an async def that never suspends: its twin's call is what running its coroutine to
        # its return would be, with no coroutine, nor anything yielded: coro_analyze)
        nm = x.kids[0]
        self.modchk(nm)
        self.read_ahead(nm.s)
        if (nm.chk or self.foreign(nm.s)) and nm.s in self.gflag:
            # (a call that may run before the def statement, as gen_call checks)
            bad = self.scalar("xor", [Val(self.mload("bool", f"@g.{nm.s}.def"), "bool"), Val("true", "bool")])
            self.guard(bad, self.unbound(nm.s))
        self.copy_private(nm.s)
        return self.call_fn(self.coro_twin(g), [], x.kids[1:], want)
    if f.direct:
        self.err(f"internal error: await in {short(f.name)}(), which coro_analyze found never suspends, is not of a call of an async def that never suspends")
    return self.await_expr(x, want, "")


def gen_await_protocol(self, n: Node, want: str) -> Val:
    # an implicit await of async with or async for (desugar_async, by n.s): of mgr.__aenter__()
    # (aenter, which first checks that the manager mgr, n's operand, has __aenter__ and
    # __aexit__, as CPython looks both up before it calls __aenter__), of mgr.__aexit__(type,
    # value, tb) for the exception the except clause around it handles (aexit), of
    # mgr.__aexit__(None, None, None) (aexitnone), of it.__anext__() (anext); or, awaiting
    # nothing, of iterator E.__aiter__() (aiter, E n's operand), which must have __anext__.
    # Where the objects do not support the protocol, CPython 3.13's TypeErrors
    if n.s.startswith("ag"):
        return self.agen_await(n, want)  # (a step of an async generator's method: asyncgens.py)
    line = n.line
    o = self.expr(n.kids[0], "")
    t = unopt(o.t)
    if is_agen(t) and (n.s == "aiter" or n.s == "anext"):
        # (an async generator is its own iterator, whose step its own code runs: asyncgens.py)
        return o if n.s == "aiter" else self.agen_step(o, "anext", Val("", ""), Val("", ""), want)
    ms = self.classes[t].methods if t in self.classes else {}
    nomgr = "'NoneType' object does not support the asynchronous context manager protocol"
    if n.s == "aiter":
        nomgr = "'async for' requires an object with __aiter__ method, got NoneType"
    elif n.s == "anext":
        nomgr = "'async for' received an object from __aiter__ that does not implement __anext__: NoneType"
    if t in self.classes:
        # (an object of a class may be None: CPython's error is NoneType's then)
        o = self.unwrap(o, "TypeError: " + nomgr)
        self.notnone(o, "TypeError: " + nomgr)
    if n.s == "aiter":
        if "__aiter__" not in ms:
            self.raise_("TypeError", self.sconst(f"'async for' requires an object with __aiter__ method, got {tname(t)}"))
            return self.await_dead(want)
        it = self.expr(mk("call", "", line, [mk("attr", "__aiter__", line, [self.vnode(o)])]), "")
        u = unopt(it.t)
        if is_agen(u):
            return it  # (an __aiter__ that is an async generator method: the one its call made)
        if u in self.classes:
            it = self.unwrap(it, "TypeError: 'async for' received an object from __aiter__ that does not implement __anext__: NoneType")
            self.notnone(it, "TypeError: 'async for' received an object from __aiter__ that does not implement __anext__: NoneType")
        if u not in self.classes or "__anext__" not in self.classes[u].methods:
            self.raise_("TypeError", self.sconst(f"'async for' received an object from __aiter__ that does not implement __anext__: {tname(u)}"))
            return self.await_dead(want)
        return it
    if n.s == "anext":
        if "__anext__" not in ms:
            self.raise_("TypeError", self.sconst(f"'async for' received an object from __aiter__ that does not implement __anext__: {tname(t)}"))
            return self.await_dead(want)
        call = mk("call", "", line, [mk("attr", "__anext__", line, [self.vnode(o)])])
        return self.await_expr(call, want, "'async for' received an invalid object from __anext__: ")
    nomgr = f"'{tname(t)}' object does not support the asynchronous context manager protocol"
    if "__aenter__" not in ms:
        self.raise_("TypeError", self.sconst(nomgr))
        return self.await_dead(want)
    if "__aexit__" not in ms:
        self.raise_("TypeError", self.sconst(nomgr + " (missed __aexit__ method)"))
        return self.await_dead(want)
    if n.s == "aenter":
        call = mk("call", "", line, [mk("attr", "__aenter__", line, [self.vnode(o)])])
        return self.await_expr(call, want, "'async with' received an object from __aenter__ that does not implement __await__: ")
    args = [mk("None", "", line, []), mk("None", "", line, []), mk("None", "", line, [])]
    if n.s == "aexit":
        # (as with_cm's __exit__: the exception's class object and the exception, and None or,
        # where __aexit__ declares that type, an object of TracebackType)
        f = ms["__aexit__"]
        tt = f.ptypes[3] if len(f.ptypes) > 3 else ""
        tb = self.vnode(self.new_obj(tt)) if tt in self.classes and shown(tt) == "_pystachy_types.TracebackType" else args[2]
        args = [mk("excinfo", "type", line, []), mk("excinfo", "value", line, []), tb]
    call = mk("call", "", line, [mk("attr", "__aexit__", line, [self.vnode(o)])] + args)
    return self.await_expr(call, want, "'async with' received an object from __aexit__ that does not implement __await__: ")


def gen_await_expr(self, x: Node, want: str, bad: str) -> Val:
    # the await of expression x's value (await_value), in the async def being compiled; bad, where
    # it is an implicit await (await_protocol): CPython's TypeError for a value that is not
    # awaitable, but for the name of its type, which ends it
    self.gencall = ""
    if bad == "" and self.agen_call(x):
        return self.agen_await_call(x, want)  # (await ag.__anext__() and the like: asyncgens.py)
    # (an empty display, which only raises the TypeError below, takes an item type of its own)
    v = self.expr(x, "list[int]" if x.kind == "list" and len(x.kids) == 0 else "dict[int,int]" if x.kind == "dict" and len(x.kids) == 0 else "")
    callee = self.gencallf if self.gencall != "" and v.v == self.gencall else None
    self.gencall = ""
    if is_coro(v.t):
        what = f"{short(callee.name)}()" if callee is not None else typestr(v.t)
        return self.await_handle(v, cyield(v.t), cret(v.t), callee, what)
    if is_gen(v.t) and callee is not None and callee.awaitable:
        if gsend(v.t) != "None":
            self.err(f"await of {short(callee.name)}(), which takes {typestr(gsend(v.t))} from send(), is not supported: a coroutine is sent None")
        r = callee.gret if callee.gret != "" else "None"
        return self.await_handle(v, gelem(v.t), r, callee, f"{short(callee.name)}()")
    if is_gen(v.t) and callee is None:
        self.err("await of a generator held in a variable is not supported: await the call of its @types.coroutine generator function")
    if v.t in self.classes and "__await__" in self.classes[v.t].methods:
        self.gencall = ""
        it = self.expr(mk("call", "", x.line, [mk("attr", "__await__", x.line, [self.vnode(v)])]), "")
        own = self.gencallf if self.gencall != "" and it.v == self.gencall else None
        self.gencall = ""
        if is_gen(it.t) and own is not None and own.awaitable:
            # (a @types.coroutine generator is a coroutine, which __await__ may not return: PEP 492)
            self.raise_("TypeError", self.sconst("__await__() returned a coroutine"))
            return self.await_dead(want)
        if is_gen(it.t) and own is not None:
            if gsend(it.t) != "None":
                self.err(f"await of {short(v.t)}, whose __await__ takes {typestr(gsend(it.t))} from send(), is not supported: a coroutine is sent None")
            r = own.gret if own.gret != "" else "None"
            return self.await_handle(it, gelem(it.t), r, own, f"{short(v.t)}.__await__()")
        if is_coro(it.t):
            self.raise_("TypeError", self.sconst("__await__() returned a coroutine"))
            return self.await_dead(want)
        self.err(f"await of {short(v.t)} is supported where its __await__ is a generator method (one that yields), not where it returns {typestr(it.t)}")
    self.raise_("TypeError", self.sconst(bad + tname(v.t) if bad != "" else f"object {tname(v.t)} can't be used in 'await' expression"))
    return self.await_dead(want)


def gen_await_dead(self, want: str) -> Val:
    # the value of an await whose awaitable raised TypeError: the code after it is not reached
    t = want if want != "" and "?" not in want else "None"
    return Val("undef" if t == BIG else "0" if t == "int" else fbits("0.0") if t == "float" else "false" if t == "bool" else "null", t)


def gen_await_handle(self, v: Val, yi: str, r: str, callee: FnInfo | None, what: str) -> Val:
    # await of coroutine (or @types.coroutine generator) v, which yields yi and returns r: this
    # coroutine runs it until it returns, yielding each value it yields to the code that runs this
    # one (Y), and passing on what is thrown into this one (throw()) or closing it (close()), as PEP
    # 380's yield from does. A coroutine made elsewhere (no callee: no call here made it) may have
    # finished, or be suspended where something else awaits it: CPython's RuntimeErrors. One a
    # call here made is destroyed once it returns, so that LLVM may put its frame in this one's
    y = self.coro_yields(yi, callee, what)
    if callee is not None and callee.ll in self.building and yi == "None":
        yi = y  # (a coroutine of the recursion being compiled: its words pass through, coro_yields)
    if callee is None and is_coro(v.t):
        p0 = self.gen_promise(v)
        s0 = self.mload("int", self.maddr("int", p0, str(GENSTATE)))
        self.guard(self.num_cmp("==", Val(s0, "int"), Val(str(GENDONE), "int")).v, "RuntimeError: " + reused(v.t))
        # (suspended where it awaits: 0, or GENCLEAN where closing it runs code of its)
        idle = self.num_cmp("==", Val(s0, "int"), Val("0", "int")).v
        clean = self.num_cmp("==", Val(s0, "int"), Val(str(GENCLEAN), "int")).v
        self.guard(self.scalar("or", [Val(idle, "bool"), Val(clean, "bool")]), "RuntimeError: coroutine is being awaited already")
    ys = self.alloca("int", "")
    yh = self.alloca("%ptr", "") if y == "int" and int_program() else ""
    head = self.label()
    done = self.label()
    susp = self.label()
    thrown = self.label() if self.eh and self.gproto else ""
    self.br(head)
    self.place(head)
    p = self.gen_next(v, done)
    self.gen_keep(self.await_words(p, yi, y, v if callee is not None else None), ys, yh)
    self.br(susp)
    self.place(susp)
    self.gen_suspend(self.mload("int", ys), 1 if self.eh else 0, v if self.eh else Val("", ""), thrown, self.mload("%ptr", yh) if yh != "" else "")
    self.br(head)
    if thrown != "":
        self.place(thrown)
        ea = self.maddr("int", self.gen_promise(Val("", "")), str(GENEXC))
        e = Val(self.mload("exc", ea), "exc")
        self.mstore("int", "0", ea)
        lx = self.label()
        lt = self.label()
        self.cbr(self.exc_match(e, self.builtin_catch("GeneratorExit")), lx, lt)
        self.place(lx)
        self.gen_close(v)
        self.throw(e)
        self.place(lt)
        p2 = self.gen_throw_into(v, e, done)
        self.gen_keep(self.await_words(p2, yi, y, v if callee is not None else None), ys, yh)
        self.br(susp)
    self.place(done)
    res = Val("null", "None") if r == "None" else self.gen_returned(v, r)
    if callee is not None:
        self.gen_drop(v)  # (it has returned: destroyed, LLVM may put its frame in this one's)
    return res


def gen_await_words(self, p: str, yi: str, y: str, owned: Val | None) -> list[str]:
    # the value in the promise at p of an awaitable that yields yi, as this coroutine, which yields
    # y, yields it on (gen_words): None is a zero slot (and a null pointer)
    if yi == "None":
        return ["0", "null" if y == "int" and int_program() else ""]
    return self.gen_words(p, yi, y, owned)


def gen_coro_method(self, o: Val, m: str, args: list[Node]) -> Val:
    # o.m(args) of coroutine o: send(None), throw(e) and close(), with which code runs a coroutine
    # (an event loop's task does). A coroutine that has finished cannot be resumed: send() and
    # throw() raise RuntimeError, where a generator's raise StopIteration
    if m == "close":
        if len(args) != 0:
            self.err(f"coroutine.close() takes no arguments ({len(args)} given)")
        if self.mcall is None or self.mcall is not self.stmtexpr:
            self.err("the value of coroutine.close() is not supported (it is what a coroutine returns as it closes): call close() as a statement")
        self.gen_close(o)
        return Val("null", "None")
    if m == "send" or m == "throw":
        if len(args) != 1 or args[0].kind == "kw" or args[0].kind == "starred":
            self.err(f"coroutine.{m}() takes exactly one argument" + (", the exception (throw(type, value, traceback) is deprecated and not supported)" if m == "throw" else ""))
        if m == "send":
            s = self.expr(args[0], "None")
            if s.t != "None":
                self.err(f"cannot send {typestr(s.t)} to {typestr(o.t)}, whose send type is None: a coroutine is sent None (an awaitable's yield takes it)")
        e = self.exc_operand(args[0]) if m == "throw" else Val("", "")
        p = self.gen_promise(o)
        s0 = self.mload("int", self.maddr("int", p, str(GENSTATE)))
        self.guard(self.num_cmp("==", Val(s0, "int"), Val(str(GENDONE), "int")).v, "RuntimeError: " + reused(o.t))
        done = self.label()
        y = cyield(o.t)
        p1 = self.gen_throw_into(o, e, done) if m == "throw" else self.gen_next(o, done)
        v = self.gen_value(p1, y) if y != "None" else Val("null", "None")
        end = self.label()
        self.br(end)
        self.place(done)
        self.gen_stop()
        self.place(end)
        return v
    self.err("coroutine.__await__() is not supported: await the coroutine" if m == "__await__" else f"'coroutine' object has no attribute '{m}'")
    return o
