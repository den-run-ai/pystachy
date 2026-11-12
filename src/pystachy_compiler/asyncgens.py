"""Async generators component of the self-hosting Pystachy compiler.

An async def whose own body yields is an async generator function (PEP 525). It compiles as a
coroutine does (coroutines.py, generators.py): one LLVM switched-resume coroutine, whose call makes
an async generator object of type agen[T,S,Y] and runs none of its body. The frame suspends in two
ways: at a yield of its own, whose value (a T) is its consumer's, and where one of its awaits
passes on what its awaitable yields (a Y) to the code that runs the coroutine that consumes it.
The word of its promise that a generator's return value would use holds which (AGFLAGS).

A consumer's step (__anext__(), asend(), athrow(), aclose() awaited, and async for) is code of
the awaiting coroutine: it resumes the frame; at a yield of its own the value is the await's; at
an await's suspension the awaiting coroutine suspends with that value and resumes the frame when it
is resumed; where the frame finishes, StopAsyncIteration. Nothing is allocated for a step. The
methods' awaitables used as values are coroutine objects of async defs that await the same step.
See docs/internals.md#async-generators.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import int_program
from src.pystachy_compiler.ir import FnInfo, Ins, Val
from src.pystachy_compiler.specs import AGCLOSE, AGFLAGS, AGRUN, AGYIELD, GENCLEAN, GENDONE, GENEXC, GENNEW, GENSEND, GENSTATE
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import ayield, cret, gelem, gsend, is_agen, is_coro, meet, targs, tname, typestr, unopt

# the methods of an async generator whose awaitables an await may run as a step of its own
AGMETHODS: list[str] = ["__anext__", "asend", "athrow", "aclose"]


def gen_agen_declare(self, f: FnInfo, d: Node) -> str:
    # async generator function f (def d, an async def whose own body yields: gen_declare has found
    # what closing it may run): its type agen[T,S,Y] (ret), T and S from its return annotation
    # (AsyncGenerator[T, S], AsyncIterator[T] or AsyncIterable[T]), else T left to its first yield
    # (ret ""); Y is what its awaits yield, None until one decides it, as a coroutine's is
    # (coro_yields). A template, as an async def is. It returns no value (Symtable rejects
    # return v). The error where Pystachy does not compile it, else ""
    f.aio = True
    f.agen = True
    f.generic = True
    f.gret = "None"
    f.gretinfer = False
    f.gsend = "None"
    if d.kids[1].kind == "noann":
        f.ret = ""
        return ""
    ta = self.agen_ann(d.kids[1], True)
    if len(ta) == 1:
        return ta[0]
    f.gsend = ta[1]
    f.ret = self.agen_type(ta[0], ta[1], "None") if ta[0] != "" else ""
    return ""


def gen_agen_type(self, t: str, s: str, y: str) -> str:
    # the type of the async generators that yield t to their consumer, take s from asend() and whose
    # awaits yield y to the code that runs it: agen[T,S,Y], shown as AsyncGenerator[T, S, Y]
    return self.ctype("agen", [t, s, y])


def gen_agen_ann(self, n: Node, infer: bool) -> list[str]:
    # [T, S] of annotation n: AsyncGenerator[T, S] or AsyncGenerator[T], AsyncIterator[T] or
    # AsyncIterable[T] (S None), typing's or collections.abc's; [why] where it is none, or Pystachy
    # does not support its types. In a function's return annotation (infer), Any in T leaves it
    # to the first yield ("")
    if n.kind == "str":
        n = self.parse_expr(n.s)
    base = self.typing_ref(n.kids[0]) if n.kind == "index" else ""
    if base != "AsyncGenerator" and base != "AsyncIterator" and base != "AsyncIterable":
        return ["an async generator function's return annotation must be AsyncIterator[T], AsyncIterable[T] or AsyncGenerator[T, S]"]
    a = n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]
    if base != "AsyncGenerator" and len(a) != 1:
        return [f"{base}[...] takes one type: {base}[T]"]
    if base == "AsyncGenerator" and len(a) != 1 and len(a) != 2:
        return ["AsyncGenerator[...] takes two types: AsyncGenerator[T, S]"]
    ti = infer and not self.dyn_policy(n.line) and self.any_in([a[0]])
    why = self.ann_problem(a[0], False) if a[0].kind != "None" and not ti else ""
    if why != "":
        return [why]
    sv = "None"
    if len(a) == 2 and a[1].kind != "None":
        why = self.ann_problem(a[1], False)
        if why != "":
            return [why]
        sv = self.ann(a[1])
        if sv != "None" and self.optional(sv) == "":
            return [f"an async generator's send type must be one that may be None (__anext__() sends None), not {typestr(sv)}"]
    return ["" if ti else "None" if a[0].kind == "None" else self.ann(a[0]), sv]


def gen_agen_landed(self, e: Val, p: str) -> None:
    # the landing block of the async generator being compiled (gen_end), whose promise is at p, where
    # exception e leaves its body: no step runs it any more, and where it is aclose()'s
    # (AGCLOSE), a GeneratorExit finishes it as a return would
    fa = self.maddr("int", p, str(AGFLAGS))
    fl = self.mload("int", fa)
    self.mstore("int", "0", fa)
    lx = self.label()
    lok = self.label()
    lgo = self.label()
    self.cbr(self.num_cmp("==", Val(fl, "int"), Val(str(AGCLOSE), "int")).v, lx, lgo)
    self.place(lx)
    self.cbr(self.exc_match(e, self.builtin_catch("GeneratorExit")), lok, lgo)
    self.place(lok)
    self.gen_ret(Val("null", "None"))
    self.place(lgo)


def gen_agen_sai(self, e: Val) -> None:
    # exception e, which leaves an async generator: a StopAsyncIteration is raised as RuntimeError
    # (PEP 525, as PEP 479 does a StopIteration), its __cause__ e where the program reads it
    ls = self.label()
    lo = self.label()
    self.cbr(self.exc_match(e, self.builtin_catch("StopAsyncIteration")), ls, lo)
    self.place(ls)
    msg = "async generator raised StopAsyncIteration"
    if not self.causeread:
        self.raise_("RuntimeError", self.sconst(msg))
    else:
        r = self.exc_value("RuntimeError", [Val(self.sconst(msg), "str")])
        self.rt("pys_exc_setcause", "void", [f"ptr {r.v}", f"ptr {e.v}"])
        self.throw(r)
    self.place(lo)


def gen_agen_raised(self, e: Val) -> None:
    # exception e, thrown into an async generator suspended where nothing handles it, raised here as
    # it leaves it: a StopIteration or StopAsyncIteration as RuntimeError
    ls = self.label()
    lo = self.label()
    self.cbr(self.exc_match(e, self.builtin_catch("StopIteration")), ls, lo)
    self.place(ls)
    self.pep479(e, "async generator")
    self.place(lo)
    self.agen_sai(e)
    self.throw(e)


def gen_agen_stop(self) -> None:
    # StopAsyncIteration, which a step raises where the async generator has finished; in an async
    # generator with exceptions off, which nothing in it can catch, the RuntimeError it becomes
    if self.curfn.agen and not self.eh:
        self.raise_("RuntimeError", self.sconst("async generator raised StopAsyncIteration"))
    else:
        self.raise_("StopAsyncIteration", self.sconst(""))


def gen_agen_close_sub(self, ag: Val, x: Val) -> None:
    # the coroutine being compiled, suspended where an await of async generator ag (in a step that
    # runs it) suspended it, is closed, or thrown GeneratorExit x: PEP 380 closes what it awaits,
    # which CPython's asend and athrow awaitables do by throwing GeneratorExit into ag. What ag
    # raises then is raised here, and if it finishes, x (close(): a GeneratorExit); if it yields
    # again, RuntimeError. No step runs it any more
    fa = self.maddr("int", self.gen_promise(ag), str(AGFLAGS))
    done = self.label()
    self.gen_throw_into(ag, self.exc_value("GeneratorExit", []) if x.v == "" else x, done)
    self.mstore("int", "0", fa)
    self.raise_("RuntimeError", self.sconst("coroutine ignored GeneratorExit"))
    self.place(done)
    self.mstore("int", "0", fa)
    if x.v == "":
        self.raise_("GeneratorExit", self.sconst(""))
    else:
        self.throw(x)


def gen_agen_result(self, t: str, mode: str, dflt: Val) -> str:
    # the type of the value of a step (agen_step) of an async generator that yields t: T, or what
    # holds T and the default; athrow()'s may be None too (an async generator that has finished
    # gives it); aclose()'s None
    if mode == "aclose":
        return "None"
    v = self.gen_value_type(t)
    if dflt.v != "":
        j = self.join(v, dflt.t)
        if j == "":
            self.err(f"anext() of an async generator of {typestr(t)} with a default of {typestr(dflt.t)}: they need one type")
        return j
    if mode == "athrow" and v != "None" and self.optional(v) != "":
        return self.optional(v)  # (a promoting int's: its box, BIGOPT)
    return v


def gen_agen_step(self, ag: Val, mode: str, arg: Val, dflt: Val, want: str, stop: str = "") -> Val:
    # await of the awaitable of async generator ag's method (mode): anext (__anext__(), anext(ag),
    # with default dflt if given), asend (asend(arg)), athrow (athrow(arg), arg an exception) or
    # aclose (aclose()), in the coroutine being compiled, as CPython's async_generator_asend and
    # async_generator_athrow run it. The step resumes ag, or throws arg into it (GeneratorExit for
    # aclose()); where ag yields a value of its own, that is the await's (aclose(): RuntimeError);
    # where an await of ag's suspends it, this coroutine yields what that yields to the code that
    # runs it, and resumes ag when it is resumed (throw() and close() of it go on to ag); where ag
    # finishes, StopAsyncIteration (aclose(): None), or anext's goes to block stop if given (an
    # async for, agen_for). A step of an async generator that a step runs already raises
    # RuntimeError
    f = self.curfn
    if not f.aio:
        self.err("'await' outside async function")
    t = gelem(ag.t)
    agy = ayield(ag.t)
    noun = "anext" if mode == "anext" or mode == "asend" else mode
    y = self.coro_yields(agy, None, f"{noun}() of {typestr(ag.t)}")
    rt = self.agen_result(t, mode, dflt)
    p = self.gen_promise(ag)
    st = self.maddr("int", p, str(GENSTATE))
    fa = self.maddr("int", p, str(AGFLAGS))
    s0 = self.mload("int", st)
    lfin = self.label()
    lgo = self.label()
    self.cbr(self.num_cmp("==", Val(s0, "int"), Val(str(GENDONE), "int")).v, lfin, lgo)
    self.place(lgo)
    running = self.num_cmp(">=", Val(self.mload("int", fa), "int"), Val(str(AGRUN), "int")).v
    self.guard(running, f"RuntimeError: {noun}(): asynchronous generator is already running")
    v = Val("null", "None")
    if mode == "asend":
        s = gsend(ag.t)
        if s == "None" and arg.t != "None":
            self.err(f"cannot send {typestr(arg.t)} to {typestr(ag.t)}, whose send type is None: annotate its async generator function -> AsyncGenerator[T, S]")
        if s != "None":
            v = self.coerce(arg, self.optional(s))
        if v.t != "None" and v.v != "null":
            lnew = self.label()
            lok = self.label()
            self.cbr(self.num_cmp("==", Val(s0, "int"), Val(str(GENNEW), "int")).v, lnew, lok)
            self.place(lnew)
            self.guard(self.ptr_cmp("!=", v, Val("null", "None")).v, "TypeError: can't send non-None value to a just-started async generator")
            self.br(lok)
            self.place(lok)
    e = arg
    lnone = self.label() if mode == "athrow" or mode == "aclose" else ""  # (where it gives None)
    if mode == "athrow" or mode == "aclose":
        if mode == "aclose":
            e = self.exc_value("GeneratorExit", [])
        # (not started, or suspended where nothing handles it: it finishes, the exception raised
        # here as it is or as it leaves it; aclose() gives None)
        lcl = self.label()
        lraw = self.label()
        self.cbr(self.num_cmp("==", Val(s0, "int"), Val(str(GENCLEAN), "int")).v if self.eh else "false", lcl, lraw)
        self.place(lraw)
        self.mstore("int", str(GENDONE), st)
        if mode == "aclose":
            self.br(lnone)
        else:
            lnew = self.label()
            lsus = self.label()
            self.cbr(self.num_cmp("==", Val(s0, "int"), Val(str(GENNEW), "int")).v, lnew, lsus)
            self.place(lnew)
            self.throw(e)
            self.place(lsus)
            self.agen_raised(e)
        self.place(lcl)
    self.mstore("int", str(AGCLOSE if mode == "aclose" else AGRUN), fa)
    sent = mode == "asend" and v.t != "None"
    if sent:
        self.mstore("int", self.to_slot(v), self.maddr("int", p, str(GENSEND)))
    ys = self.alloca("int", "")
    yh = self.alloca("%ptr", "") if y == "int" and int_program() else ""
    after = self.label()
    done = self.label()
    head = self.label()
    susp = self.label()
    thrown = self.label() if self.eh and self.gproto else ""
    closed = self.label() if self.eh else ""
    if mode == "athrow" or mode == "aclose":
        self.gen_throw_into(ag, e, done)
    else:
        self.gen_next(ag, done)
    self.br(after)
    self.place(head)
    self.gen_next(ag, done)
    self.br(after)
    self.place(after)
    p1 = self.gen_promise(ag)
    if sent:
        self.mstore("int", "0", self.maddr("int", p1, str(GENSEND)))  # (taken where it resumed)
    lgot = self.label()
    lpass = self.label()
    self.cbr(self.num_cmp("==", Val(self.mload("int", self.maddr("int", p1, str(AGFLAGS))), "int"), Val(str(AGYIELD), "int")).v, lgot, lpass)
    self.place(lpass)
    self.gen_keep(self.await_words(p1, agy, y, None), ys, yh)
    self.br(susp)
    self.place(susp)
    self.gen_suspend(self.mload("int", ys), 1 if self.eh else 0, Val("", ""), thrown, self.mload("%ptr", yh) if yh != "" else "", closed)
    self.br(head)
    if thrown != "":
        # (throw() of this coroutine, suspended where ag's await suspended: thrown into ag, whose
        # await passes it on; GeneratorExit closes ag, then is raised here, PEP 380)
        self.place(thrown)
        ea = self.maddr("int", self.gen_promise(Val("", "")), str(GENEXC))
        x = Val(self.mload("exc", ea), "exc")
        self.mstore("int", "0", ea)
        lx = self.label()
        lt = self.label()
        self.cbr(self.exc_match(x, self.builtin_catch("GeneratorExit")), lx, lt)
        self.place(lx)
        self.agen_close_sub(ag, x)
        self.place(lt)
        self.gen_throw_into(ag, x, done)
        self.br(after)
    if closed != "":
        self.place(closed)
        self.agen_close_sub(ag, Val("", ""))
    lend = self.label()
    ph = Ins("phi", rt, "")
    self.place(lgot)
    if mode == "aclose":
        self.raise_("RuntimeError", self.sconst("async generator ignored GeneratorExit"))
    else:
        got = self.gen_value(self.gen_promise(ag), t) if t != "None" else Val("null", "None")
        if rt != "None":
            got = self.coerce(got, rt)
            self.incoming(ph, got.v, self.cur)
        self.br(lend)
    # (it finishes in this step: no step runs it any more; athrow() raises StopAsyncIteration)
    self.place(done)
    self.mstore("int", "0", fa)
    if mode == "athrow":
        self.agen_stop()
    else:
        self.br(lfin)
    # (it has finished: anext() and asend() raise StopAsyncIteration, or give the default, or go
    # to stop; athrow() and aclose() give None)
    self.place(lfin)
    if mode == "athrow" or mode == "aclose":
        self.br(lnone)
    elif dflt.v != "":
        d = self.coerce(dflt, rt)
        if rt != "None":
            self.incoming(ph, d.v, self.cur)
        self.br(lend)
    elif stop != "":
        self.br(stop)
    else:
        self.agen_stop()
    if lnone != "":
        self.place(lnone)
        if rt != "None":
            nv = self.coerce(Val("null", "None"), rt)
            self.incoming(ph, nv.v, self.cur)
        self.br(lend)
    self.place(lend)
    if rt == "None":
        return Val("null", "None")
    return Val(self.phi(ph), rt)


def gen_agen_args(self, m: str, args: list[Node]) -> None:
    # the arguments of async generator method m's call, as CPython checks them
    for a in args:
        if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
            self.err(f"async_generator.{m}() takes no keyword or unpacked arguments")
    if (m == "__anext__" or m == "aclose" or m == "__aiter__") and len(args) != 0:
        self.err(f"async_generator.{m}() takes no arguments ({len(args)} given)")
    if m == "asend" and len(args) != 1:
        self.err(f"async_generator.asend() takes exactly one argument ({len(args)} given)")
    if m == "athrow" and len(args) != 1:
        self.err("async_generator.athrow() takes one argument, the exception (athrow(type, value, traceback) is deprecated and not supported)")


def gen_agen_await(self, n: Node, want: str) -> Val:
    # await node n of a method's awaitable that agen_awaitable makes (s: agnext, agsend, agthrow or
    # agclose): the step of the async generator, its first operand, with the value or the
    # exception that its second gives (anext's: the default)
    ag = self.expr(n.kids[0], "")
    if not is_agen(ag.t):
        self.err(f"internal error: {n.s} of {typestr(ag.t)}")
    mode = "a" + n.s[2:]
    x = self.expr(n.kids[1], "") if len(n.kids) > 1 else Val("", "")
    if mode == "anext":
        return self.agen_step(ag, mode, Val("", ""), x, want)
    return self.agen_step(ag, mode, x, Val("", ""), want)


def gen_agen_call(self, x: Node) -> bool:
    # is awaited expression x the call of an async generator's __anext__(), asend(), athrow() or
    # aclose(), or anext() of one: its await runs the step itself (agen_await_call), with no
    # awaitable made
    if x.kind != "call":
        return False
    c = x.kids[0]
    if c.kind == "attr" and c.s in AGMETHODS and self.dotted(c) == "":
        return is_agen(self.dry(c.kids[0]))
    if c.kind == "name" and c.s == "anext" and not self.bound("anext") and (len(x.kids) == 2 or len(x.kids) == 3):
        for a in x.kids[1:]:
            if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
                return False
        return is_agen(self.dry(x.kids[1]))
    return False


def gen_agen_await_call(self, x: Node, want: str) -> Val:
    # await of call x (agen_call): the async generator, the method's argument, then the step
    c = x.kids[0]
    if c.kind == "name":
        ag = self.expr(x.kids[1], "")
        d = self.expr(x.kids[2], "") if len(x.kids) == 3 else Val("", "")
        return self.agen_step(ag, "anext", Val("", ""), d, want)
    ag = self.expr(c.kids[0], "")
    m = c.s
    args = x.kids[1:]
    self.agen_args(m, args)
    if m == "__anext__":
        return self.agen_step(ag, "anext", Val("", ""), Val("", ""), want)
    if m == "asend":
        return self.agen_step(ag, "asend", self.expr(args[0], self.optional(gsend(ag.t)) if gsend(ag.t) != "None" else ""), Val("", ""), want)
    if m == "athrow":
        return self.agen_step(ag, "athrow", self.exc_operand(args[0]), Val("", ""), want)
    return self.agen_step(ag, "aclose", Val("", ""), Val("", ""), want)


def gen_agen_method(self, o: Val, m: str, args: list[Node]) -> Val:
    # o.m(args) of async generator o: __aiter__() is o; __anext__(), asend(v), athrow(e) and
    # aclose() make the awaitable whose await runs that step (agen_awaitable)
    if m != "__aiter__" and m not in AGMETHODS:
        self.err(f"'async_generator' object has no attribute '{m}'")
    self.agen_args(m, args)
    if m == "__aiter__":
        return o
    if m == "__anext__":
        return self.agen_awaitable(o, "anext", [])
    if m == "asend":
        return self.agen_awaitable(o, "asend", [self.vnode(self.expr(args[0], self.optional(gsend(o.t)) if gsend(o.t) != "None" else ""))])
    if m == "athrow":
        return self.agen_awaitable(o, "athrow", [self.vnode(self.exc_operand(args[0]))])
    return self.agen_awaitable(o, "aclose", [])


def gen_agen_awaitable(self, o: Val, mode: str, extra: list[Node]) -> Val:
    # the awaitable of async generator o's method (mode, agen_step), with its argument extra (a
    # val node), as a value: a coroutine object of an async def made here, which awaits the step
    # (an await node of kind ag<mode>). Its type, coro[Y,None,R,K], has the mark K of the method
    # (coro_mark): CPython's async_generator_asend or async_generator_athrow, which it shows and
    # which CPython's messages name
    line = self.line
    noann = mk("noann", "", line, [])
    ps = [mk("param", ".0", line, [noann, noann])]
    ks = [mk("name", ".0", line, [])]
    for j in range(len(extra)):
        ps.append(mk("param", f".{j + 1}", line, [noann, noann]))
        ks.append(mk("name", f".{j + 1}", line, []))
    aw = mk("await", "ag" + mode[1:], line, ks)
    body = [mk("expr", "", line, [aw])] if mode == "aclose" else [mk("return", "", line, [aw])]
    name = "__anext__" if mode == "anext" else mode
    d = mk("def", name, line, [mk("params", "0,-1", line, ps), noann, mk("block", "", line, body), mk("deco", "async", line, [])])
    f = self.curfn
    g = self.declare_fn(d, "")
    self.ngenexp += 1
    g.ll = f"@f.agen.{name}.{self.ngenexp}"
    g.mod = f.mod
    g.home = self.fn_home(f)
    c = self.call_fn(g, [], [self.vnode(o)] + extra)
    a = targs(c.t)
    return Val(c.v, self.ctype("coro", [a[0], a[1], a[2], "athrow" if mode == "athrow" or mode == "aclose" else "asend"]))


def gen_aiter_(self, args: list[Node]) -> Val:
    # aiter(x): x's asynchronous iterator, what its __aiter__() returns (an async generator is its own)
    if len(args) != 1 or args[0].kind == "kw" or args[0].kind == "starred" or args[0].kind == "dstar":
        self.err(f"aiter expected 1 argument, got {len(args)}" if len(args) != 1 else "aiter() takes no keyword or unpacked arguments")
    v = self.expr(args[0], "")
    if is_agen(v.t):
        return v
    t = unopt(v.t)
    if t in self.classes and "__aiter__" in self.classes[t].methods:
        v = self.unwrap(v, "TypeError: 'NoneType' object is not an async iterable")
        self.notnone(v, "TypeError: 'NoneType' object is not an async iterable")
        it = self.expr(mk("call", "", self.line, [mk("attr", "__aiter__", self.line, [self.vnode(v)])]), "")
        u = unopt(it.t)
        if is_agen(u) or (u in self.classes and "__anext__" in self.classes[u].methods):
            return it
        self.raise_("TypeError", self.sconst(f"aiter() returned not an async iterator of type '{tname(u)}'"))
        return it
    self.raise_("TypeError", self.sconst(f"'{tname(t)}' object is not an async iterable"))
    return v


def gen_anext_(self, args: list[Node]) -> Val:
    # anext(it[, default]): the awaitable of its next item, it.__anext__()'s; with a default, one
    # that gives the default where it raises StopAsyncIteration
    for a in args:
        if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
            self.err("anext() takes no keyword or unpacked arguments")
    if len(args) != 1 and len(args) != 2:
        self.err(f"anext expected at least 1 argument, got {len(args)}" if len(args) == 0 else f"anext expected at most 2 arguments, got {len(args)}")
    v = self.expr(args[0], "")
    if is_agen(v.t):
        return self.agen_awaitable(v, "anext", [self.vnode(self.expr(args[1], ""))] if len(args) == 2 else [])
    t = unopt(v.t)
    if t in self.classes and "__anext__" in self.classes[t].methods:
        v = self.unwrap(v, "TypeError: 'NoneType' object is not an async iterator")
        self.notnone(v, "TypeError: 'NoneType' object is not an async iterator")
        if len(args) == 1:
            return self.expr(mk("call", "", self.line, [mk("attr", "__anext__", self.line, [self.vnode(v)])]), "")
        return self.anext_default(v, self.expr(args[1], ""))
    self.raise_("TypeError", self.sconst(f"'{tname(t)}' object is not an async iterator"))
    return v


def gen_anext_default(self, it: Val, d: Val) -> Val:
    # anext(it, d) of an object it of a class with __anext__: a coroutine object of an async def
    # made here, which awaits it.__anext__() and returns what it gives, or d where it raises
    # StopAsyncIteration (the builtin class, whatever the program names so: a made name)
    line = self.line
    noann = mk("noann", "", line, [])
    ps = [mk("param", ".0", line, [noann, noann]), mk("param", ".1", line, [noann, noann])]
    step = mk("await", "", line, [mk("call", "", line, [mk("attr", "__anext__", line, [mk("name", ".0", line, [])])])])
    stop = mk("name", "StopAsyncIteration", line, [])
    stop.made = True
    body = [mk("try", "", line, [mk("block", "", line, [mk("return", "", line, [step])]), mk("except", "", line, [stop, mk("block", "", line, [mk("return", "", line, [mk("name", ".1", line, [])])])])])]
    dn = mk("def", "anext", line, [mk("params", "0,-1", line, ps), noann, mk("block", "", line, body), mk("deco", "async", line, [])])
    f = self.curfn
    # (it returns what holds both the item and the default, as an annotation would say)
    ct = self.dry(mk("call", "", line, [mk("attr", "__anext__", line, [self.vnode(it)])]))
    r = self.join(cret(ct), d.t) if is_coro(ct) else ""
    if is_coro(ct) and r == "":
        self.err(f"anext() of an async iterator of {typestr(cret(ct))} with a default of {typestr(d.t)}: they need one type")
    g = self.declare_fn(dn, "")
    if r != "":
        g.gret = r
        g.gretinfer = False
        g.ret = self.coro_type("None", r)
    self.ngenexp += 1
    g.ll = f"@f.anext.{self.ngenexp}"
    g.mod = f.mod
    g.home = self.fn_home(f)
    return self.call_fn(g, [], [self.vnode(it), self.vnode(d)])


def gen_agen_for(self, n: Node) -> bool:
    # try statement n, if it is the step of an async for (desugar_async's async_for: try: v =
    # await it.__anext__() except StopAsyncIteration: running = False else: target = v; body)
    # whose iterator is an async generator: compiled without raising and catching
    # StopAsyncIteration, its step going to the except clause's block where the async generator
    # has finished (agen_step), and with nothing to mark (pys_try_mark), as the rest of that step
    # raises no StopAsyncIteration that the clause would catch. Else False: an ordinary try
    if len(n.kids) != 3 or n.kids[1].kind != "except" or n.kids[2].kind != "block" or n.kids[2].s != "else" or n.s != "":
        return False
    b = n.kids[0].kids
    if len(b) != 1 or b[0].kind != "assign" or len(b[0].kids) != 2:
        return False
    aw = b[0].kids[1]
    c = n.kids[1].kids[0]
    if aw.kind != "await" or aw.s != "anext" or aw.kids[0].kind != "name" or c.kind != "name" or not c.made or c.s != "StopAsyncIteration":
        return False
    if not is_agen(self.ltype.get(aw.kids[0].s, "")):
        return False  # (the iterator's local, desugar_async's, which no other code assigns)
    before = dict(self.narrowed)
    ends: list[dict[str, str]] = []
    lstop = self.label()
    done = self.label()
    self.line = aw.line
    ag = self.expr(aw.kids[0], "")
    self.assign(b[0].kids[0], self.agen_step(ag, "anext", Val("", ""), Val("", ""), "", lstop))
    self.stmts(n.kids[2].kids)
    if not self.term:
        ends.append(self.narrowed)
        self.br(done)
    self.place(lstop)
    self.narrowed = before
    self.stmts(n.kids[1].kids[1].kids)
    if not self.term:
        ends.append(self.narrowed)
        self.br(done)
    if len(ends) > 0:
        self.place(done)
        self.narrowed = meet(ends)
    else:
        self.narrowed = {}
    return True


def gen_agen_aiter(self, e: Node) -> Val:
    # the iterable e of a comprehension's async for clause (an await node of kind aiterc,
    # desugar_comp): what its __aiter__() gives, as async for checks it (await_protocol), which a
    # for loop steps through with awaits (for_seq). An iterator object that is no async generator
    # is stepped through by one that yields what its __anext__() gives (agen_adapter)
    dead = self.term
    it = self.await_protocol(mk("await", "aiter", e.line, [e]), "")
    if self.term and not dead:
        # (await_protocol raised CPython's TypeError: the loop, whose items have no type, would be
        # code that never runs)
        self.err(f"an async for clause of a comprehension over {tname(unopt(self.dry(e)))} is not supported: it is no asynchronous iterable (CPython raises TypeError)")
    if is_agen(unopt(it.t)):
        return it
    return self.agen_adapter(it)


def gen_agen_adapter(self, it: Val) -> Val:
    # an async generator that yields what iterator object it's __anext__() gives until that raises
    # StopAsyncIteration (the builtin class, whatever the program binds to its name: a made name),
    # for a comprehension's async for clause (agen_aiter). Its locals' names hold a dot, as no
    # variable's of the program can
    line = self.line
    noann = mk("noann", "", line, [])
    run = "__pys_ac.run"
    val = "__pys_ac.val"
    stop = mk("name", "StopAsyncIteration", line, [])
    stop.made = True
    step = mk("block", "", line, [mk("assign", "", line, [mk("name", val, line, []), mk("await", "anext", line, [mk("name", ".0", line, [])])])])
    end = mk("except", "", line, [stop, mk("block", "", line, [mk("assign", "", line, [mk("name", run, line, []), mk("False", "", line, [])])])])
    each = mk("block", "else", line, [mk("expr", "", line, [mk("yield", "", line, [mk("name", val, line, [])])])])
    loop = mk("while", "", line, [mk("name", run, line, []), mk("block", "", line, [mk("try", "", line, [step, end, each])])])
    body = [mk("assign", "", line, [mk("name", run, line, []), mk("True", "", line, [])]), loop]
    d = mk("def", "__aiter__", line, [mk("params", "0,-1", line, [mk("param", ".0", line, [noann, noann])]), noann, mk("block", "", line, body), mk("deco", "async", line, [])])
    f = self.curfn
    g = self.declare_fn(d, "")
    self.ngenexp += 1
    g.ll = f"@f.agen.aiter.{self.ngenexp}"
    g.mod = f.mod
    g.home = self.fn_home(f)
    return self.call_fn(g, [], [self.vnode(it)])


def gen_agen_param(self, n: Node) -> bool:
    # is annotation n AsyncIterator[T], AsyncIterable[T] or AsyncGenerator[T, S] (typing's or
    # collections.abc's, also quoted): a template's parameter so annotated takes each call's
    # argument's type (declare_fn), as no annotation names what an async generator's awaits yield
    if n.kind == "str":
        if "[" not in n.s:
            return False
        n = self.parse_expr(n.s)
    if n.kind != "index":
        return False
    base = self.typing_ref(n.kids[0])
    return base == "AsyncIterator" or base == "AsyncIterable" or base == "AsyncGenerator"
