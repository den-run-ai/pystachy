"""Generators component of the self-hosting Pystachy compiler.

A generator function compiles to an LLVM switched-resume coroutine (llvm.coro.*). The typed IR
marks where it starts (gen.start), suspends (gen.yield) and finishes (gen.ret); LLVM's coroutine
passes compute what lives across each yield, lay the frame out and outline the resume and
destroy functions (CoroSplit), and may put the frame of a generator a loop owns in the loop's
own frame (CoroElide). The frame comes from pys_alloc, which the collector scans; nothing frees
it (coro.free has nothing to do). A consumer resumes the handle (gen.resume) and reads the
promise (gen.promise): the value yielded, the state, the value returned; close(), send() and
throw() give it a command or a value there before they resume it. See
docs/internals.md#generators.
"""
from __future__ import annotations
from src.pystachy_compiler.analysis import closure_free, comp_shared, comp_unbound
from src.pystachy_compiler.diagnostics import int_program
from src.pystachy_compiler.ir import Exit, FnInfo, Ins, IterArg, SeqStart, Try, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import (
    BIG,
    EXCBASES,
    GENCLEAN,
    GENCLOSEC,
    GENCMD,
    GENDONE,
    GENEXC,
    GENNAME,
    GENNEW,
    GENRET,
    GENRETP,
    GENRUN,
    GENSEND,
    GENSTATE,
    GENTHROWC,
    GENVALP,
    exc_derives,
)
from src.pystachy_compiler.syntax import Node, comp_names, has_kind, made_var, mk, names_in
from src.pystachy_compiler.utils import gelem, gsend, is_gen, is_list, typestr


def with_yield(body: list[Node]) -> bool:
    # does one of these statements yield inside a with block
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass" or st.kind == "lambda":
            continue
        if st.kind == "with" and has_kind(st.kids[-1], "yield"):
            return True
        for k in st.kids:
            if (k.kind == "block" and with_yield(k.kids)) or (k.kind == "except" and with_yield(k.kids[1].kids)):
                return True
    return False


def loop_yield(body: list[Node]) -> bool:
    # does one of these statements yield inside a for loop over a call (which may make a
    # generator the loop owns, closed where the loop is left)
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass" or st.kind == "lambda":
            continue
        if st.kind == "for" and has_kind(st.kids[2], "yield") and st.kids[1].kind != "list" and st.kids[1].kind != "tuple" and st.kids[1].kind != "str":
            return True
        for k in st.kids:
            if (k.kind == "block" and loop_yield(k.kids)) or (k.kind == "except" and loop_yield(k.kids[1].kids)):
                return True
    return False


def yields_from(n: Node) -> bool:
    # does n hold a yield from (outside the functions it defines)
    if n.kind == "yield" and n.s == "from":
        return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    for k in n.kids:
        if yields_from(k):
            return True
    return False


def uses_protocol(n: Node) -> bool:
    # does code n use the generator protocol beyond iteration and close() (Gen.gproto): a call of
    # a method named send or throw (of any object: what it is is not known before the types are).
    # Without one, nothing sends a generator a value: a yield's value is None
    if n.kind == "call" and n.kids[0].kind == "attr" and (n.kids[0].s == "send" or n.kids[0].s == "throw"):
        return True
    for k in n.kids:
        if uses_protocol(k):
            return True
    return False


def reads_handled(n: Node) -> bool:
    # does code n call sys.exception() (Gen.excread), which tells a generator's own exception
    # being handled from its resumer's
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].s == "exception" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == "sys":
        return True
    for k in n.kids:
        if reads_handled(k):
            return True
    return False


def reads_cause(n: Node) -> bool:
    # does code n read an attribute named __cause__ (Gen.causeread)
    if n.kind == "attr" and n.s == "__cause__":
        return True
    for k in n.kids:
        if reads_cause(k):
            return True
    return False


def gen_pep479(self, e: Val) -> None:
    # PEP 479's RuntimeError, raised for StopIteration e that leaves a generator: its __cause__
    # is e where the program reads it (Gen.causeread)
    if not self.causeread:
        self.raise_("RuntimeError", self.sconst("generator raised StopIteration"))
        return
    r = self.exc_value("RuntimeError", [Val(self.sconst("generator raised StopIteration"), "str")])
    self.rt("pys_exc_setcause", "void", [f"ptr {r.v}", f"ptr {e.v}"])
    self.throw(r)


def gen_exc_mark(self) -> str:
    # the exception being handled where a try statement starts, which its clauses' ends restore
    # (exc_back): in a generator of a program that reads it (Gen.excread), null where it is its
    # resumer's (the generator handles none of its own), as that resumer may differ by then
    h = self.rt("pys_exc_handled", "ptr", [])
    if not self.excread or self.fn.gouter == "":
        return h
    same = self.ptr_cmp("==", Val(h, "exc"), Val(self.mload("%ptr", self.fn.gouter), "exc")).v
    return self.select(same, Val("null", "exc"), Val(h, "exc"))


def gen_exc_back(self, old: str) -> None:
    # the exception being handled is old (exc_mark) again: in a generator of a program that reads
    # it, null is its resumer's now
    if self.excread and self.fn.gouter != "":
        none = self.ptr_cmp("==", Val(old, "exc"), Val("null", "exc")).v
        old = self.select(none, Val(self.mload("%ptr", self.fn.gouter), "exc"), Val(old, "exc"))
    self.rt("pys_exc_restore", "void", [f"ptr {old}"])


def comp_clauses(c: Node, body: list[Node], inline: bool) -> list[Node]:
    # body inside the clauses of comprehension c after its first iterable (c.kids[3:]: if
    # clauses, and for clauses nested in their order): if statements, and for loops of a
    # function of its own (genexp_value) or, inline, compfor loops, whose targets are their own
    # as gen_listcomp nests them
    line = c.line
    for j in range(len(c.kids) - 1, 2, -1):
        x = c.kids[j]
        inner = mk("block", "", line, body)
        if x.kind == "compfor" and inline:
            shared: list[str] = []
            comp_shared(c, j, shared)
            body = [mk("compfor", "", line, [x.kids[0], x.kids[1], inner, mk("names", " ".join(shared), line, [])])]
        elif x.kind == "compfor":
            body = [mk("for", "", line, [x.kids[0], x.kids[1], inner])]
        else:
            body = [mk("if", "", line, [x.kids[0] if x.kind == "compif" else x, inner, mk("block", "", line, [])])]
    return body


def fresh_list_yields(n: Node) -> bool:
    # A yield context may choose a fresh list's layout before it exists. Existing
    # objects must keep their layout and aliases; nested functions have their own
    # callers. A forwarding yield-from call checks its callee by the same rule.
    if n.kind == "yield":
        return len(n.kids) == 1 and ((n.s != "from" and n.kids[0].kind == "list") or (n.s == "from" and n.kids[0].kind == "call"))
    for k in n.kids:
        if k.kind not in ["def", "class", "subclass", "lambda"] and not fresh_list_yields(k):
            return False
    return True


def fresh_yield_context(f: FnInfo, want: str) -> bool:
    # Generator[list[Any], S, R] -> Generator[list[T], S, R] only for fresh
    # yielded displays, allocated directly in the requested storage. This is a
    # specialization of a call, never a conversion of an existing generator/list.
    if not f.gen or not is_gen(f.ret) or not is_gen(want) or "?" in want:
        return False
    if gelem(f.ret) != "list[dyn]" or not is_list(gelem(want)) or gelem(want) == "list[dyn]" or gsend(f.ret) != gsend(want):
        return False
    return fresh_list_yields(f.orig.kids[2] if f.pending else f.node.kids[2])


def gen_gen_declare(self, f: FnInfo, d: Node) -> str:
    # generator function f (def d): its yield type (f.ret, gen[Y]) and return type (f.gret) from
    # its return annotation, or left for its calls to decide (a template); what closing it may
    # run (f.gclose, f.gwith). The error where Pystachy does not compile it, else ""
    f.gen = True
    body = d.kids[2].kids
    f.gwith = with_yield(body)
    f.gclose = f.gwith or yields_from(d.kids[2]) or loop_yield(body)
    for st in body:
        f.gtry = f.gtry or has_kind(st, "try")
    f.gclose = f.gclose or f.gtry
    if len(d.kids) > 3 and d.kids[3].s == "async":
        return "async generators are not supported"
    if d.kids[1].kind == "noann":
        f.generic = True  # (its first yield decides what it yields, for each call's argument types)
        f.ret = ""
        f.gret = ""
        f.gretinfer = True
        return ""
    yr = self.gen_ann_ret(d.kids[1], True)
    if len(yr) == 1:
        return yr[0]
    f.ret = self.gen_type(yr[0], yr[2]) if yr[0] != "" else ""
    f.gret = yr[1]
    f.gretinfer = yr[1] == ""
    f.gsend = yr[2]
    if yr[0] == "" or f.gretinfer:
        f.generic = True
    return ""


def gen_gen_type(self, y: str, s: str) -> str:
    # the type of the generators that yield y and take s from send(): gen[Y], or gen[Y,S] where S
    # is not None (a generator whose yields' values are S | None, None being what next() sends)
    return self.ctype("gen", [y] if s == "None" else [y, s])


def gen_gen_ann_ret(self, n: Node, infer: bool = False) -> list[str]:
    # [Y, R, S] of a generator's return annotation n: Iterator[Y] or Iterable[Y] (R and S None),
    # Generator[Y, S, R] or Generator[Y] (typing's or collections.abc's); [why] where it is no
    # such annotation, or Pystachy does not support its types. In a function's annotation,
    # Any in Y or R leaves that channel inferred (""); S needs a concrete native layout.
    if n.kind == "str":
        n = self.parse_expr(n.s)
    base = self.typing_ref(n.kids[0]) if n.kind == "index" else ""
    if base != "Iterator" and base != "Iterable" and base != "Generator":
        return ["a generator function's return annotation must be Iterator[T], Iterable[T] or Generator[Y, S, R]"]
    a = n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]
    if base != "Generator" and len(a) != 1:
        return [f"{base}[...] takes one type: {base}[T]"]
    if base == "Generator" and len(a) != 1 and len(a) != 3:
        return ["Generator[...] takes three types: Generator[Y, S, R]"]
    infer = infer and not self.dyn_policy(n.line)  # (a module that compiles Any as dynamic values: a dyn channel)
    yi = infer and self.any_in([a[0]])
    why = self.ann_problem(a[0], False) if a[0].kind != "None" and not yi else ""
    if why != "":
        return [why]
    sv = "None"
    if len(a) == 3 and a[1].kind != "None":
        if infer and self.any_in([a[1]]):
            return ["a generator's send type cannot contain Any: annotate Generator[Y, S, R] with a concrete send type S that may be None (for example str | None); future send() calls cannot infer it"]
        why = self.ann_problem(a[1], False)
        if why != "":
            return [why]
        sv = self.ann(a[1])
        if sv != "None" and self.optional(sv) == "":
            return [f"a generator's send type must be one that may be None (next() sends None), not {typestr(sv)}"]
    r = "None"
    if len(a) == 3 and a[2].kind != "None":
        if infer and self.any_in([a[2]]):
            r = ""
        else:
            why = self.ann_problem(a[2], False)
            if why != "":
                return [why]
            r = self.ann(a[2])
    return ["" if yi else "None" if a[0].kind == "None" else self.ann(a[0]), r, sv]


def gen_gen_name(self, f: FnInfo) -> str:
    # what CPython shows of f's generator objects: its __qualname__
    q = self.qualname(f)
    return q[: q.find("@")] if "@" in q else q


def gen_gen_begin(self, f: FnInfo) -> None:
    # the start of generator function f's code, its parameters stored: gen.start makes the
    # generator object (its frame, from pys_alloc) and suspends it before the first statement
    # (a call runs none of the body). With exceptions on, a landing block covers the body: what
    # leaves the body finishes the generator (gen_end)
    fn = self.fn
    fn.coro = True
    if self.eh and not self.rtmode:
        fn.gdepth = self.alloca("int", "")
    i = Ins("gen.start", "", "")
    i.a = [Val(self.sconst(self.gen_name(f)), "str")]
    first = self.label()
    i.b = [first]
    self.runtime("pys_alloc")
    self.add(i)
    self.term = True
    if self.eh:
        fn.gbase = self.alloca("int", "")
        if f.gwith:
            fn.gsaved = self.alloca("%ptr", "")
        if f.gtry:
            fn.gouter = self.alloca("exc", "")
            fn.ghand = self.alloca("exc", "")
        fn.gpad = self.label()
        tr = Try(first)
        tr.landing = fn.gpad
        fn.tries.append(tr)
        self.handler = fn.gpad
    self.place(first)
    self.gen_enter()


def gen_gen_enter(self) -> None:
    # where a generator resumes: the depth of the unwind actions now (its try statements' marks
    # are relative to it), on which those it set aside go back (pys_gen_enter)
    fn = self.fn
    if fn.gdepth != "":
        # The consumer has entered this activation before setting GENRUN. A resumed
        # coroutine may have a different caller depth from the previous yield.
        self.mstore("int", self.rt("pys_recursion_depth", "i64", []), fn.gdepth)
    if fn.gbase == "":
        return
    if fn.gsaved != "":
        b = self.rt("pys_gen_enter", "i64", [f"ptr {self.mload('%ptr', fn.gsaved)}"])
    else:
        b = self.rt("pys_try_mark", "i64", [])
    self.mstore("int", b, fn.gbase)
    if fn.gouter != "":
        # (the exception its resumer handles, which it handles again at its next suspend; a
        # yield in an except clause or a finally block handles its own again)
        self.mstore("%ptr", self.rt("pys_exc_handled", "ptr", []), fn.gouter)
        if len(self.excs) > 0:
            self.rt("pys_exc_restore", "void", [f"ptr {self.mload('%ptr', fn.ghand)}"])


def gen_gen_end(self, f: FnInfo) -> None:
    # the end of generator function f's code: falling off its end finishes it. Its landing block
    # (exceptions on): an exception that leaves its body finishes it too. Closed by its loop (a
    # command, gen.drop), the GeneratorExit raised at its yield ends it, and anything else is
    # reported as CPython reports an exception it ignores; else the exception goes on, a
    # StopIteration as RuntimeError (PEP 479)
    fn = self.fn
    if not self.term:
        self.gen_none_end()
        self.gen_ret(Val("null", "None"))
    if f.ret == "":
        f.ret = self.gen_type("None", f.gsend)  # (no yield is reached: it yields nothing)
    if f.gret == "":
        f.gret = "None"
    elif fn.gnone and f.gret != "None" and f.gretinfer:
        f.gret = self.optional(f.gret)  # (it also ends without a value: R | None, the same pointer)
    if fn.gpad != "":
        self.handler = ""
        slot = self.alloca("exc", "")
        e = self.landing(fn.gpad, slot, Val("0", "int"))
        p = self.gen_promise(Val("", ""))
        self.mstore("int", str(GENDONE), self.maddr("int", p, str(GENSTATE)))
        cmd = self.mload("int", self.maddr("int", p, str(GENCMD)))
        lc = self.label()
        lp = self.label()
        self.cbr(self.num_cmp("!=", Val(cmd, "int"), Val("0", "int")).v, lc, lp)
        self.place(lc)
        lf = self.label()
        lr = self.label()
        self.cbr(self.exc_match(e, self.builtin_catch("GeneratorExit")), lf, lr)
        self.place(lr)
        name = self.mload("%ptr", self.maddr("int", p, str(GENNAME)))
        self.rt("pys_gen_unraisable", "void", [f"ptr {e.v}", f"ptr {name}", f"ptr {p}"])
        self.br(lf)
        self.place(lf)
        self.gen_ret(Val("null", "None"))
        self.place(lp)
        ls = self.label()
        lo = self.label()
        self.cbr(self.exc_match(e, self.builtin_catch("StopIteration")), ls, lo)
        self.place(ls)
        self.pep479(e)
        self.place(lo)
        self.throw(e)
    f.noret = False


def gen_builtin_catch(self, b: str) -> str:
    # the classes an except clause naming builtin exception class b catches (catch_set)
    out: list[str] = []
    for k in EXCBASES:
        if exc_derives(k, b):
            out.append(k)
    for k in self.classes:
        if self.classes[k].exc != "" and self.derives(k, b):
            out.append(k)
    return "\x01" + "\x01".join(out) + "\x01"


def gen_gen_promise(self, h: Val) -> str:
    # the address of the promise of generator h ("": the generator being compiled's own)
    i = Ins("gen.promise", "%ptr", "")
    if h.v != "":
        i.a = [h]
    self.put(i, 1)
    return f"%t{i.r[0]}"


def gen_gen_unhandle(self) -> None:
    # before the generator being compiled suspends: the exception being handled is its resumer's
    # again (in an except clause or a finally block, its own is kept for where it resumes)
    fn = self.fn
    if fn.gouter == "":
        return
    if len(self.excs) > 0:
        self.mstore("%ptr", self.rt("pys_exc_handled", "ptr", []), fn.ghand)
    self.rt("pys_exc_restore", "void", [f"ptr {self.mload('%ptr', fn.gouter)}"])


def gen_gen_ret(self, v: Val) -> None:
    # the generator being compiled finishes, returning v: its final suspend
    self.gen_unhandle()
    i = Ins("gen.ret", "", "")
    if v.t == BIG:
        i.a = [Val(self.big_lo(v).v, "%slot"), Val(self.big_hi(v).v, "%ptr")]  # (GENRETP)
    elif v.t != "None":
        i.a = [Val(self.to_slot(v), "%slot")]
    self.put(i, 2)
    self.term = True


def gen_gen_none_end(self) -> None:
    # the generator ends without a value here (return, or the end of its code): the value of a
    # yield from that delegates to it is None, which its return type must hold. An unannotated
    # one returning a reference type R elsewhere returns R | None (the same null pointer); one
    # returning a number would need a box: an error
    f = self.curfn
    r = f.gret
    if r != "" and r != "None" and self.optional(r) != r and (not f.gretinfer or not self.none_null(r)):
        self.err(f"{short(f.name)}() returns {typestr(r)} and ends without a value elsewhere: annotate it Generator[Y, {typestr(f.gsend)}, {typestr(r)} | None]" if not f.gretinfer else f"{short(f.name)}() returns {typestr(r)} and ends without a value elsewhere, which the value of yield from cannot hold: return a value on every path, or annotate it Generator[Y, {typestr(f.gsend)}, {typestr(r)} | None]")
    self.fn.gnone = True


def gen_none_null(self, t: str) -> bool:
    # is t | None the same pointer as t, None being null (str, containers, tuples; not numbers)
    o = self.optional(t)
    return o != "" and (o == t or not self.isnum(t))


def gen_gen_return(self, n: Node) -> None:
    # return [v] in a generator: it finishes, with v the value of the yield from that delegates to it
    f = self.curfn
    v = Val("null", "None")
    if len(n.kids) > 0 and n.kids[0].kind != "None":
        r = f.gret
        v = self.expr(n.kids[0], r if r != "None" else "")
        if (r == "" or r == "None") and v.t == "None":
            self.gen_none_end()  # (return f(), return (yield): a value that is None, as a return without one)
        elif r == "None":
            self.err(f"{short(f.name)}() is annotated to return no value (Iterator[T], Iterable[T] or Generator[Y, {'None' if f.gsend == 'None' else 'S'}, None]): annotate it Generator[Y, {typestr(f.gsend)}, R] to return one")
        elif r == "":
            if "?" in v.t:
                self.err(f"cannot infer what {short(f.name)}() returns from {typestr(v.t)}; annotate it Generator[Y, {typestr(f.gsend)}, R]")
            if self.fn.gnone and self.optional(v.t) != v.t and not self.none_null(v.t):
                self.err(f"{short(f.name)}() returns {typestr(v.t)} and ends without a value elsewhere, which the value of yield from cannot hold: return a value on every path, or annotate it Generator[Y, {typestr(f.gsend)}, {typestr(v.t)} | None]")
            f.gret = v.t
        else:
            v = self.coerce(v, r)
    else:
        self.gen_none_end()
    self.carried = v  # (the value first: a finally block runs after it is computed)
    ended = self.leave(0)
    v = self.carried
    self.carried = Val("", "")
    if not ended:
        self.gen_ret(v)
    self.term = True


def gen_gen_cleanup(self) -> int:
    # 1 where closing the generator being compiled runs code of its (GeneratorExit raised here
    # reaches a try statement, a with block or a loop that owns a generator), else 0: with
    # exceptions off, nothing can
    if not self.eh:
        return 0
    if self.handler != self.fn.gpad:
        return 1
    for x in self.exits:
        if x.kind == "with":
            return 1
    return 0


def gen_gen_suspend(self, slot: str, k: int, sub: Val, thrown: str = "", hi: str = "") -> None:
    # the generator being compiled yields the value in slot (with hi, the pointer of an int in a
    # program where a module opts in to promoting ints: gen_slots), then goes on where it is resumed.
    # k: closing it here runs code of its (gen_cleanup), so a close raises GeneratorExit here,
    # having closed sub first, the generator a yield from delegates to (or none: Val("", "")):
    # what closing sub raises is raised here (PEP 380). In a program that uses throw()
    # (Gen.gproto), the exception thrown into it is raised here too, or handed to thrown, the
    # block of a yield from that throws it into its generator
    fn = self.fn
    if fn.gsaved != "":
        sv = self.rt("pys_gen_leave", "ptr", [f"i64 {self.mload('int', fn.gbase)}"])
        self.mstore("%ptr", sv, fn.gsaved)
    self.gen_unhandle()
    res = self.label()
    i = Ins("gen.yield", "", "")
    i.a = [Val(slot, "%slot")] + ([Val(hi, "%ptr")] if hi != "" else [])
    i.k = k
    i.b = [res]
    self.put(i, 2)
    self.term = True
    self.place(res)
    self.gen_enter()
    if k == 1:
        p = self.gen_promise(Val("", ""))
        cmd = self.mload("int", self.maddr("int", p, str(GENCMD)))
        lx = self.label()
        lgo = self.label()
        self.cbr(self.num_cmp("!=", Val(cmd, "int"), Val("0", "int")).v, lx, lgo)
        self.place(lx)
        if self.gproto:
            # throw(): the command is done once the exception is raised here (or thrown on)
            lt = self.label()
            lc = self.label()
            ca = self.maddr("int", p, str(GENCMD))
            self.cbr(self.num_cmp("==", Val(cmd, "int"), Val(str(GENTHROWC), "int")).v, lt, lc)
            self.place(lt)
            self.mstore("int", "0", ca)
            if thrown != "":
                self.br(thrown)
            else:
                ea = self.maddr("int", p, str(GENEXC))
                e = Val(self.mload("exc", ea), "exc")
                self.mstore("int", "0", ea)
                self.throw(e)
            self.place(lc)
        if sub.v != "":
            self.gen_close(sub)
            self.gen_drop(sub)
        self.raise_("GeneratorExit", self.sconst(""))
        self.place(lgo)


def gen_yield_value(self, n: Node) -> Val:
    # the value of yield v (yield, (yield)) in an expression: what send() sent to the generator as
    # it resumed it (None from next(), a for loop and throw()), of type S | None for a generator
    # whose send type is S; None where S is None (Iterator[T], Generator[Y, None, R], no annotation)
    f = self.curfn
    if n.s == "from":
        self.err("the value of yield from is supported assigned to a variable (r = yield from g()); a yield from elsewhere in an expression is not")
    self.yield_stmt(n)
    if f.gsend == "None":
        return Val("null", "None")
    t = self.optional(f.gsend)
    if self.term:
        return Val("undef", t)
    if not self.gproto:
        # next() and loops send None: dynamic storage needs its box, not null.
        return Val(self.rtdata("pys_dyn_none_box") if t == "dyn" else "null", t)
    p = self.gen_promise(Val("", ""))
    v = self.from_slot(self.mload("int", self.maddr("int", p, str(GENSEND))), t)
    if t == "dyn":
        # next()/throw() clear the shared send slot to zero. An explicit send()
        # has already boxed its argument; only the implicit None needs boxing.
        empty = self.ptr_cmp("==", v, Val("null", "dyn")).v
        return Val(self.select(empty, Val(self.rtdata("pys_dyn_none_box"), "dyn"), v), "dyn")
    return v


def gen_yield_stmt(self, n: Node) -> None:
    # yield v as a statement (its value, None as next() resumes it, is dropped), or yield from x
    f = self.curfn
    if not f.gen:
        self.err("'yield' outside function")
    if n.s == "from":
        self.yield_from(n.kids[0])
        return
    dead = self.term  # (after a return, raise, break or continue: it is never reached)
    y = gelem(f.ret) if f.ret != "" else ""
    v = self.expr(n.kids[0], y) if len(n.kids) > 0 else Val("null", "None")
    if y == "":
        if "?" in v.t:
            self.err(f"cannot infer what {short(f.name)}() yields from an empty {typestr(v.t)}; annotate it -> Iterator[T]")
        y = v.t
        f.ret = self.gen_type(y, f.gsend)
    elif v.t != y and not (v.t == BIG and y == "int"):
        v = self.coerce(v, y)
    if dead:
        # (return v; yield: the yield makes a generator function, which never suspends there,
        # so the code after it is not reached either: not an end without a value, gen_end)
        self.unreachable()
        return
    w = ["0", ""] if y == "None" else self.gen_slots(v, gelem(f.ret))
    self.gen_suspend(w[0], self.gen_cleanup(), Val("", ""), "", w[1])


def gen_yield_from(self, x: Node) -> Val:
    # yield from x: x a generator, delegated to until it finishes (its return value is the
    # result), else any iterable, each item of which is yielded (the result is None)
    f = self.curfn
    if not f.gen:
        self.err("'yield' outside function")
    y = gelem(f.ret) if f.ret != "" else ""
    if self.is_mapcall(x):
        x = self.mapgen(x)  # (map(f, xs) or filter(f, xs): the generator expression it is)
    if x.kind == "listcomp" and x.s == "gen":
        # yield from (e for t in it if c ...): each e, as the loops the generator expression is
        # would make it (its first iterable at once, the rest as it goes on; t its own variable)
        own: list[str] = []
        names_in(x.kids[1], own)
        names: list[str] = []
        comp_names(x, names)
        if comp_unbound(x, names) != "":
            self.err(comp_unbound(x, names))
        body = comp_clauses(x, [mk("expr", "", x.line, [mk("yield", "", x.line, [x.kids[0]])])], True)
        self.hidden_loop(mk("for", "", x.line, [x.kids[1], x.kids[2], mk("block", "", x.line, body)]), own, names)
        return Val("null", "None")
    if self.iterator_call(x):
        # yield from range(...), enumerate(...), zip(...) or reversed(...): each item, as a for
        # loop over the call takes it
        self.yield_from_iter(x.kids[0].s + "()")
        it = mk("name", "__yf", x.line, [])
        self.hidden_loop(mk("for", "", x.line, [it, x, mk("block", "", x.line, [mk("expr", "", x.line, [mk("yield", "", x.line, [mk("name", "__yf", x.line, [])])])])]), ["__yf"], ["__yf"])
        return Val("null", "None")
    self.gencall = ""
    v = self.expr(x, self.gen_type(y, f.gsend) if y != "" and self.dyn_policy(x.line) else "")
    callee = self.gencallf if v.v == self.gencall and self.gencall != "" else None
    if not is_gen(v.t):
        self.yield_from_iter(typestr(v.t))
        it = mk("name", "__yf", x.line, [])
        self.hidden_loop(mk("for", "", x.line, [it, self.vnode(v), mk("block", "", x.line, [mk("expr", "", x.line, [mk("yield", "", x.line, [mk("name", "__yf", x.line, [])])])])]), ["__yf"], ["__yf"])
        return Val("null", "None")
    t = gelem(v.t)
    if y == "":
        y = t
        f.ret = self.gen_type(y, f.gsend)
    dynamic = (y == "dyn" and self.dyn_boxable(t) == "") or (t == "dyn" and self.dyn_unboxable(y))
    if t != y and not self.widens(t, y) and not dynamic:
        self.err(f"{short(f.name)}() yields {typestr(y)}, but yield from delegates to a generator that yields {typestr(t)}")
    if self.gproto:
        return self.yield_from_proto(v, t, y, callee)
    head = self.label()
    done = self.label()
    self.br(head)
    self.place(head)
    p = self.gen_next(v, done)
    w = self.gen_words(p, t, y, v if callee is not None else None)
    self.gen_suspend(w[0], 1 if self.eh else 0, v if self.eh else Val("", ""), "", w[1])
    self.br(head)
    self.place(done)
    r = callee.gret if callee is not None else ""
    res = Val("null", "None") if r == "None" else Val("", "")
    if r != "" and r != "None":
        res = self.gen_returned(v, r)
    if callee is not None:
        self.gen_drop(v)  # (it has finished: destroyed, LLVM may put its frame in this one's)
    return res


def gen_yield_from_proto(self, v: Val, t: str, y: str, callee: FnInfo | None) -> Val:
    # yield from v, generator v that yields t, in a generator that yields y, in a program that uses
    # send() or throw() (Gen.gproto), as PEP 380 delegates: what is sent to this generator is sent
    # on to v, an exception thrown into it is thrown into v (GeneratorExit closes v, then is raised
    # here), and closing it closes v first; what v raises is raised here. Its value, the value
    # v returns (where its type is known: callee)
    f = self.curfn
    fs = f.gsend
    if fs != "None" and gsend(v.t) != fs:
        self.err(f"{short(f.name)}() takes {typestr(fs)} from send(), which yield from sends on to a generator that takes {typestr(gsend(v.t))}: annotate them with the same send type")
    ys = self.alloca("int", "")
    yh = self.alloca("%ptr", "") if y == "int" and int_program() else ""  # (the pointer: gen_slots)
    head = self.label()
    done = self.label()
    susp = self.label()
    thrown = self.label() if self.eh else ""
    self.br(head)
    self.place(head)
    p = self.gen_next(v, done)
    if fs != "None":
        self.mstore("int", "0", self.maddr("int", p, str(GENSEND)))  # (taken where v resumed)
    self.gen_keep(self.gen_words(p, t, y, v if callee is not None else None), ys, yh)
    self.br(susp)
    self.place(susp)
    self.gen_suspend(self.mload("int", ys), 1 if self.eh else 0, v if self.eh else Val("", ""), thrown, self.mload("%ptr", yh) if yh != "" else "")
    if fs != "None":
        own = self.gen_promise(Val("", ""))
        x = self.mload("int", self.maddr("int", own, str(GENSEND)))
        self.mstore("int", x, self.maddr("int", self.gen_promise(v), str(GENSEND)))
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
        self.gen_keep(self.gen_words(p2, t, y, v if callee is not None else None), ys, yh)
        self.br(susp)
    self.place(done)
    r = callee.gret if callee is not None else ""
    res = Val("null", "None") if r == "None" else Val("", "")
    if r != "" and r != "None":
        res = self.gen_returned(v, r)
    if callee is not None:
        self.gen_drop(v)
    return res


def gen_gen_keep(self, w: list[str], ys: str, yh: str) -> None:
    # the slot and pointer w of the value a yield from yields (gen_words) in ys and yh (if any)
    self.mstore("int", w[0], ys)
    if yh != "":
        self.mstore("%ptr", w[1], yh)


def gen_gen_slots(self, v: Val, y: str) -> list[str]:
    # v as the promise of a generator that yields y holds it: its slot, and where y is an int in
    # a program where a module opts in to promoting ints (int_program), its pointer (GENVALP; null
    # where it fits, as every yield of an int writes it), else ""
    if y != "int" or not int_program():
        return [self.to_slot(v), ""]
    if v.t == BIG:
        return [self.big_lo(v).v, self.big_hi(v).v]
    return [self.to_slot(v), "null"]


def gen_gen_words(self, p: str, t: str, y: str, owned: Val | None = None) -> list[str]:
    # the value in the promise at p of a generator that yields t, as the promise of one that yields
    # y holds it (yield from: gen_slots): an int's pointer goes on with its slot
    s = self.mload("int", p)
    hi = self.mload("%ptr", self.maddr("int", p, str(GENVALP))) if t == "int" and int_program() else ""
    if t == y:
        return [s, hi]
    # A dynamic conversion can raise before gen_suspend installs the delegate's
    # close path. Drop a freshly owned delegate on that exceptional edge; an
    # existing generator belongs to its caller and must remain resumable.
    outer = self.handler
    failed = ""
    slot = ""
    mark = Val("", "")
    if owned is not None and self.eh and (t == "dyn" or y == "dyn"):
        mark = Val(self.rt("pys_try_mark", "i64", []), "int")
        if self.fn.gbase != "":
            mark = Val(self.scalar("sub", [mark, Val(self.mload("int", self.fn.gbase), "int")]), "int")
        slot = self.alloca("exc", "")
        failed = self.label()
        tr = Try(self.label())
        tr.final = failed
        self.fn.tries.append(tr)
        self.handler = failed
        self.place(tr.body)
    result = self.gen_slots(self.coerce(self.big(Val(s, "int"), hi) if hi != "" else self.from_slot(s, t), y), y)
    if failed != "" and owned is not None:
        self.handler = outer
        done = self.label()
        self.br(done)
        error = self.landing(failed, slot, mark)
        self.gen_drop(owned)
        self.throw(error)
        self.place(done)
    return result


def gen_gen_value(self, p: str, t: str) -> Val:
    # the value in the promise at p of a generator that yields t: where t is an int in a program
    # where a module opts in, the promoting int of its slot and pointer (GENVALP), narrowed in a
    # module that does not opt in but for lib's READ_HELPERS (bigints.read_policy, gen_value_type)
    s = self.mload("int", p)
    if t != "int" or not int_program():
        return self.from_slot(s, t)
    v = self.big(Val(s, "int"), self.mload("%ptr", self.maddr("int", p, str(GENVALP))))
    return v if self.read_policy() else self.big_narrow(v)


def gen_gen_value_type(self, t: str) -> str:
    # the type of the value that gen_value reads of a generator that yields t, here
    return BIG if t == "int" and int_program() and self.read_policy() else t


def gen_gen_returned(self, h: Val, r: str) -> Val:
    # the value that finished generator h returned, of type r (the value of a yield from): a
    # promoting int's pointer is in GENRETP
    pr = self.gen_promise(h)
    s = self.mload("int", self.maddr("int", pr, str(GENRET)))
    if r == BIG:
        return self.big(Val(s, "int"), self.mload("%ptr", self.maddr("int", pr, str(GENRETP))))
    return self.from_slot(s, r)


def gen_yield_from_iter(self, what: str) -> None:
    # yield from an iterator that is no generator (of what), in the generator being compiled: one
    # that takes a value from send() would send it on to that iterator, which has no send()
    f = self.curfn
    if f.gsend != "None":
        self.err(f"yield from {what} in {short(f.name)}(), which takes {typestr(f.gsend)} from send(), is not supported: PEP 380 sends the value on to the iterator, which has no send() (iterate it with for and yield each item)")


def gen_hidden_loop(self, loop: Node, own: list[str], names: list[str]) -> None:
    # for loop loop, whose variables are its own, as a comprehension's are (gen_listcomp): own,
    # its target's, and names, those of the compfor loops in its body too
    saved: list[str] = []
    held: list[int] = []
    boxes: list[str] = []
    for nm in names:
        saved.append(self.ltype.get(nm, "") + " " + self.lreg.get(nm, ""))
        held.append(self.compvars.get(nm, 0))
        boxes.append(self.idbox.get(nm, ""))
    pre = self.narrowed
    share = self.compshare
    self.compshare = {}
    self.for_(loop, own)
    self.compshare = share
    self.narrowed = pre
    for i in range(len(names)):
        nm = names[i]
        sp = saved[i].find(" ")
        if sp == 0:
            if nm in self.ltype:
                del self.ltype[nm]
        else:
            self.ltype[nm] = saved[i][:sp]
            self.lreg[nm] = saved[i][sp + 1 :]
        if held[i] > 0:
            self.compvars[nm] = held[i]
        elif nm in self.compvars:
            del self.compvars[nm]
        if boxes[i] != "":
            self.idbox[nm] = boxes[i]
        else:
            self.idbox.pop(nm, "")


def gen_gen_next(self, h: Val, done: str) -> str:
    # the next step of generator h: done if it has finished (so a finished generator is never
    # resumed), else it is resumed (a ValueError if it is running: it resumed itself), and done
    # if it finishes then. The address of its promise, where the value it yielded is
    p = self.gen_promise(h)
    st = self.maddr("int", p, str(GENSTATE))
    s0 = self.mload("int", st)
    go = self.label()
    self.cbr(self.num_cmp("==", Val(s0, "int"), Val(str(GENDONE), "int")).v, done, go)
    self.place(go)
    self.guard(self.num_cmp("==", Val(s0, "int"), Val(str(GENRUN), "int")).v, "ValueError: generator already executing")
    self.rt("pys_recursion_enter", "i64", [])
    self.mstore("int", str(GENRUN), st)
    i = Ins("gen.resume", "", "")
    i.a = [h]
    self.add(i)
    self.rt("pys_recursion_leave", "void", [])
    s1 = self.mload("int", st)
    got = self.label()
    self.cbr(self.num_cmp("==", Val(s1, "int"), Val(str(GENDONE), "int")).v, done, got)
    self.place(got)
    return p


def gen_gen_drop(self, h: Val) -> None:
    # generator h, which a loop owns, is left: closed (where it is suspended in a try statement,
    # a with block or a loop of its own: GeneratorExit is raised there), and destroyed
    i = Ins("gen.drop", "", "")
    i.a = [h]
    self.runtime("pys_exc_handled")
    self.runtime("pys_exc_restore")
    self.runtime("pys_gen_ignored")
    for name in ["pys_recursion_enter", "pys_recursion_leave", "pys_recursion_depth", "pys_recursion_restore",
                 "pys_try_mark", "pys_exc_begin", "pys_gen_unraisable", "pys_personality"]:
        self.runtime(name)
    self.add(i)


def gen_owned_gen(self, v: Val, it: Node) -> int:
    # does a loop over v, the value of node it, own it: a generator that a call of a generator
    # function (or an __iter__ that is one) has just made (or a val node of one, gen_owned_node).
    # 0: no; 1: yes; 2: yes, and closing it may run code of its (with exceptions on)
    if not is_gen(v.t):
        return 0
    f = self.gencallf if self.gencall != "" and v.v == self.gencall else self.vowned[it.s] if it.kind == "val" and it.s in self.vowned else None
    if it.kind == "name" and it.s == ".0" and self.curfn.gfirst is not None:
        f = self.curfn.gfirst  # (a generator expression's first iterable, a generator it alone holds)
    if f is None:
        return 0
    return 2 if self.eh and f.gclose else 1


def gen_owned_node(self, v: Val) -> Node:
    # a val node of v, a value just computed: if it is a generator that a loop over it owns
    # (owned_gen), so does the loop over this node
    own = self.gencallf if is_gen(v.t) and self.gencall != "" and v.v == self.gencall else None
    n = self.vnode(v)
    if own is not None:
        self.vowned[n.s] = own
    return n


def gen_owned_loop(self, owned: list[Val], close: bool, tgt: Node, seqs: list[Val], mode: str, body: list[Node], start: str, hide: list[str], arg: IterArg | None, made: SeqStart | None) -> None:
    # a for loop over generators it owns (owned, made just now by calls), which are dropped
    # (gen.drop: closed, the last first, then destroyed) where the loop is left: at its end, at
    # break and at return, before the code after it, as CPython closes them once the loop drops
    # them; with close (one may run code as it closes, gen_cleanup), also where an exception
    # leaves the body: the loop is the body of a try statement whose finally block drops them.
    # (Destroyed on every way out, LLVM's CoroElide may put their frames in this function's.)
    drops = [mk("gendrop", "", self.line, [self.vnode(owned[j])]) for j in range(len(owned) - 1, -1, -1)]
    mark = Val("", "")
    slot = ""
    outer = self.handler
    hf = ""
    if close:
        mark = Val(self.rt("pys_try_mark", "i64", []), "int")
        if self.fn.gbase != "":
            mark = Val(self.scalar("sub", [mark, Val(self.mload("int", self.fn.gbase), "int")]), "int")
        slot = self.alloca("exc", "")
        hf = self.label()
    fx = Exit("finally", "", outer)
    fx.body = drops
    fx.nloops = len(self.loops)
    fx.nexcs = len(self.excs)
    self.exits.append(fx)
    tr = Try(self.label())
    if close:
        tr.final = hf
        self.fn.tries.append(tr)
        self.handler = hf
    ek = self.elsekids
    eb = self.elsebrk
    brk = ""
    if body is self.elsekids:
        # (for ... else: break skips the else block, which runs after the loop's end: it drops them first)
        brk = self.label()
        self.elsebrk = brk
    self.place(tr.body)
    self.for_seq(tgt, seqs, mode, body, start, hide, arg, made)
    self.elsekids = ek
    self.elsebrk = eb
    self.exits.pop()
    self.handler = outer
    tr.exit = self.label()
    if not self.term:
        self.stmts(drops)
    self.br(tr.exit)
    if brk != "":
        self.place(brk)
        self.stmts(drops)
        self.br(eb)
    if close:
        e = self.landing(hf, slot, mark)
        self.stmts(drops)
        self.throw(e)
    self.place(tr.exit)


def gen_gen_list(self, v: Val, want: str) -> Val:
    # the items of generator v, as a fresh list (list(g), sorted(g), "".join(g), ...)
    it = mk("name", "__item", self.line, [])
    return self.listcomp(mk("listcomp", "", self.line, [it, made_var("__item", self.line), self.vnode(v)]), want if want != "" else self.ctype("list", [gelem(v.t)]))


def gen_gen_stream(self, name: str, v: Val, args: list[Node], want: str, resultsoft: bool) -> Val:
    # sum(g), min(g), max(g), any(g), all(g), ... of generator v: of the generator expression
    # (x for x in g), whose items they take as they come (any() and all() stop at the deciding one)
    it = mk("name", "__item", self.line, [])
    g = mk("listcomp", "gen", self.line, [it, made_var("__item", self.line), self.owned_node(v)])
    return self.builtin(name, [g] + args, want, resultsoft)


def gen_gen_unpack(self, t: Node, g: Val) -> None:
    # a, b = g of generator g: an item for each target, then one more step, which must find g
    # finished (else there are too many values); CPython takes them all before it stores the
    # first (the targets of t, a tuple or list node with no starred one)
    n = len(t.kids)
    y = gelem(g.t)
    got = self.alloca("int", "")
    few = self.label()
    ok = self.label()
    items: list[Val] = []
    for i in range(n + 1):
        self.mstore("int", str(i), got)
        p = self.gen_next(g, few if i < n else ok)
        if i == n:
            self.raise_("ValueError", self.sconst(f"too many values to unpack (expected {n})"))
        elif y == "None":
            items.append(Val("null", "None"))
        else:
            sl = self.alloca(self.gen_value_type(y), "")
            self.mstore(self.gen_value_type(y), self.gen_value(p, y).v, sl)
            items.append(Val(sl, self.gen_value_type(y)))
    self.place(few)
    k = self.to_str(Val(self.mload("int", got), "int"))
    msg = self.cat(self.cat(Val(self.sconst(f"not enough values to unpack (expected {n}, got "), "str"), k), Val(self.sconst(")"), "str"))
    self.raise_("ValueError", msg.v)
    self.place(ok)
    for i in range(n):
        self.assign(t.kids[i], items[i] if y == "None" else Val(self.mload(items[i].t, items[i].v), items[i].t))


def gen_gen_contains(self, x: Val, g: Val) -> Val:
    # x in g of generator g: it is iterated until an item equals x (CPython's == of the item and x)
    gn = self.owned_node(g)
    item = made_var("__item", self.line)
    test = mk("cmp", "==", self.line, [mk("name", "__item", self.line, []), self.vnode(x)])
    return self.builtin("any", [mk("listcomp", "gen", self.line, [test, item, gn])], "bool")


def gen_gen_method(self, o: Val, m: str, args: list[Node]) -> Val:
    # o.m(args) of generator o: __next__() is next(o), __iter__() o itself, close(), throw(e)
    # and send(v)
    if m == "close":
        if len(args) != 0:
            self.err(f"generator.close() takes no arguments ({len(args)} given)")
        if self.mcall is None or self.mcall is not self.stmtexpr:
            self.err("the value of generator.close() is not supported (it is what a generator returns as it closes): call close() as a statement")
        self.gen_close(o)
        return Val("null", "None")
    if (m == "send" or m == "throw") and not self.gproto:
        self.err(f"generator.{m}() is supported where it is called (g.{m}(...)), not as a value")
    if m == "throw":
        return self.gen_throw(o, args)
    if m == "send":
        return self.gen_send(o, args)
    if m == "__next__" and len(args) == 0:
        return self.gen_next_value(o, Val("", ""))
    if m == "__iter__" and len(args) == 0:
        return o
    self.err(f"'generator' object has no attribute '{m}'")
    return o


def gen_gen_next_value(self, g: Val, dflt: Val) -> Val:
    # next(g) of generator g: the value it yields next; where it has finished, dflt (next(g, d))
    # if given (Val("", "") if not), else StopIteration (in a generator with exceptions off,
    # which nothing in it can catch, PEP 479's RuntimeError at once)
    y = gelem(g.t)
    done = self.label()
    p = self.gen_next(g, done)
    v = self.gen_value(p, y)
    y = BIG if v.t == BIG else y
    t = y if dflt.v == "" else self.join(y, dflt.t)
    if t == "":
        self.err(f"next() of a generator of {typestr(y)} with a default of {typestr(dflt.t)}: they need one type")
    if dflt.v != "":
        v = self.coerce(v, t)
    got = self.cur
    end = self.label()
    self.br(end)
    self.place(done)
    if dflt.v == "":
        self.gen_stop()
        self.place(end)
        return v
    d = self.coerce(dflt, t)
    dl = self.cur
    self.br(end)
    self.place(end)
    if t == "None":
        return Val("null", "None")
    ph = Ins("phi", t, "")
    self.incoming(ph, v.v, got)
    self.incoming(ph, d.v, dl)
    return Val(self.phi(ph), t)


def gen_gen_stop(self) -> None:
    # StopIteration, which next(), send() and throw() of a generator raise once it has finished
    # (in a generator with exceptions off, which nothing in it can catch, PEP 479's RuntimeError
    # at once)
    if self.curfn.gen and not self.eh:
        self.raise_("RuntimeError", self.sconst("generator raised StopIteration"))
    else:
        self.raise_("StopIteration", self.sconst(""))


def gen_gen_raised(self, e: Val) -> None:
    # exception e, which leaves a generator, raised here: a StopIteration as PEP 479's RuntimeError
    ls = self.label()
    lo = self.label()
    self.cbr(self.exc_match(e, self.builtin_catch("StopIteration")), ls, lo)
    self.place(ls)
    self.pep479(e)
    self.place(lo)
    self.throw(e)


def gen_gen_close(self, h: Val) -> None:
    # h.close() of generator h (also as a yield from closes the generator it delegates to): one
    # suspended where closing it runs code of its (GENCLEAN) is resumed with close()'s command, which
    # raises GeneratorExit at its yield; what it raises then is raised here (its landing block
    # leaves it for pys_gen_closed: a StopIteration as RuntimeError), and if it yields instead,
    # RuntimeError (it stays suspended there). Any other one (not started, suspended where nothing
    # handles GeneratorExit, finished) is finished at once; a running one raises ValueError
    p = self.gen_promise(h)
    st = self.maddr("int", p, str(GENSTATE))
    s0 = self.mload("int", st)
    self.guard(self.num_cmp("==", Val(s0, "int"), Val(str(GENRUN), "int")).v, "ValueError: generator already executing")
    fin = self.label()
    if self.eh:
        # (with exceptions off, no yield is in a try or with block: nothing runs as one closes)
        end = self.label()
        go = self.label()
        self.cbr(self.num_cmp("==", Val(s0, "int"), Val(str(GENCLEAN), "int")).v, go, fin)
        self.place(go)
        self.rt("pys_recursion_enter", "i64", [])
        ca = self.maddr("int", p, str(GENCMD))
        self.mstore("int", str(GENCLOSEC), ca)
        self.mstore("int", str(GENRUN), st)
        x = self.rt("pys_exc_handled", "ptr", [])
        i = Ins("gen.resume", "", "")
        i.a = [h]
        self.add(i)
        self.rt("pys_recursion_leave", "void", [])
        self.rt("pys_exc_restore", "void", [f"ptr {x}"])
        e = Val(self.rt("pys_gen_closed", "ptr", []), "exc")
        lr = self.label()
        lok = self.label()
        self.cbr(self.ptr_cmp("!=", e, Val("null", "None")).v, lr, lok)
        self.place(lr)
        self.gen_raised(e)
        self.place(lok)
        s1 = self.mload("int", st)
        lign = self.label()
        self.cbr(self.num_cmp("!=", Val(s1, "int"), Val(str(GENDONE), "int")).v, lign, end)
        self.place(lign)
        self.mstore("int", "0", ca)
        self.raise_("RuntimeError", self.sconst("generator ignored GeneratorExit"))
        self.place(fin)
        self.mstore("int", str(GENDONE), st)
        self.br(end)
        self.place(end)
        return
    self.br(fin)
    self.place(fin)
    self.mstore("int", str(GENDONE), st)


def gen_exc_operand(self, e: Node) -> Val:
    # the exception that raise e would raise, as a value (throw(e)): an exception, or an
    # exception class (whose call without arguments makes it) or a call of one
    k = self.exc_class(e)
    if k == "" or k in self.classes:
        v = self.exc_value_of(e, k)
        if v.t in self.classes and self.classes[v.t].exc != "":
            v = self.exc_of(v)
        if v.t != "exc":
            self.err("exceptions must derive from BaseException: throw() needs an exception, an exception class or a call of one")
        return v
    name = e.kids[0].s if e.kind == "call" else e.s
    vals = self.exc_vals(self.exc_args(e), name)
    if name == "SystemExit":
        return self.exit_value(vals)
    return self.exc_value("OSError" if name == "IOError" or name == "EnvironmentError" else name, vals)


def gen_gen_throw_into(self, h: Val, e: Val, done: str) -> str:
    # exception e thrown into generator h (Gen.gproto): raised at the yield where h is suspended,
    # if a try, with or yield from there may handle it (GENCLEAN): it is resumed with throw()'s
    # command, and goes to done if it finishes then, else (it yields again) the address of its
    # promise is returned. Elsewhere nothing in h handles it: it is raised here as it is (h has not
    # started, or has finished), or as it leaves h (suspended at a yield outside any handler: a
    # StopIteration as RuntimeError), and h is finished. A running one raises ValueError
    p = self.gen_promise(h)
    st = self.maddr("int", p, str(GENSTATE))
    s0 = self.mload("int", st)
    self.guard(self.num_cmp("==", Val(s0, "int"), Val(str(GENRUN), "int")).v, "ValueError: generator already executing")
    go = self.label()
    lnot = self.label()
    self.cbr(self.num_cmp("==", Val(s0, "int"), Val(str(GENCLEAN), "int")).v if self.eh else "false", go, lnot)
    self.place(lnot)
    lsusp = self.label()
    lraw = self.label()
    self.cbr(self.num_cmp("==", Val(s0, "int"), Val("0", "int")).v, lsusp, lraw)
    self.place(lsusp)
    self.mstore("int", str(GENDONE), st)
    self.gen_raised(e)
    self.place(lraw)
    self.mstore("int", str(GENDONE), st)
    self.throw(e)
    self.place(go)
    self.rt("pys_recursion_enter", "i64", [])
    self.mstore("int", str(GENTHROWC), self.maddr("int", p, str(GENCMD)))
    self.mstore("exc", e.v, self.maddr("int", p, str(GENEXC)))
    self.mstore("int", str(GENRUN), st)
    i = Ins("gen.resume", "", "")
    i.a = [h]
    self.add(i)
    self.rt("pys_recursion_leave", "void", [])
    s1 = self.mload("int", st)
    got = self.label()
    self.cbr(self.num_cmp("==", Val(s1, "int"), Val(str(GENDONE), "int")).v, done, got)
    self.place(got)
    return p


def gen_gen_throw(self, g: Val, args: list[Node]) -> Val:
    # g.throw(e) of generator g: e raised where g is suspended (gen_throw_into); the value g yields
    # next, or StopIteration if it finishes
    if len(args) != 1 or args[0].kind == "kw" or args[0].kind == "starred":
        self.err("generator.throw() takes one argument, the exception (throw(type, value, traceback) is deprecated and not supported)")
    e = self.exc_operand(args[0])
    done = self.label()
    p = self.gen_throw_into(g, e, done)
    v = self.gen_value(p, gelem(g.t))
    end = self.label()
    self.br(end)
    self.place(done)
    self.gen_stop()
    self.place(end)
    return v


def gen_gen_send(self, g: Val, args: list[Node]) -> Val:
    # g.send(v) of generator g: g resumed with v, which the yield where it is suspended gives (an
    # S | None of a generator whose send type is S); the value g yields next, or StopIteration if
    # it finishes. send(None) is next(g); a value other than None cannot start g (TypeError)
    if len(args) != 1 or args[0].kind == "kw" or args[0].kind == "starred":
        self.err("generator.send() takes exactly one argument")
    s = gsend(g.t)
    if s == "None":
        v = self.expr(args[0], "None")
        if v.t != "None":
            self.err(f"cannot send {typestr(v.t)} to {typestr(g.t)}, whose send type is None: annotate its generator function -> Generator[Y, S, R]")
        return self.gen_next_value(g, Val("", ""))
    ot = self.optional(s)
    v = self.coerce(self.expr(args[0], ot), ot)
    p = self.gen_promise(g)
    if v.t != "None" and v.v != "null":
        lnew = self.label()
        lok = self.label()
        s0 = self.mload("int", self.maddr("int", p, str(GENSTATE)))
        self.cbr(self.num_cmp("==", Val(s0, "int"), Val(str(GENNEW), "int")).v, lnew, lok)
        self.place(lnew)
        self.guard(self.ptr_cmp("!=", v, Val("null", "None")).v, "TypeError: can't send non-None value to a just-started generator")
        self.br(lok)
        self.place(lok)
    sa = self.maddr("int", p, str(GENSEND))
    self.mstore("int", self.to_slot(v), sa)
    done = self.label()
    self.gen_next(g, done)
    self.mstore("int", "0", sa)  # (taken where g resumed)
    r = self.gen_value(p, gelem(g.t))
    end = self.label()
    self.br(end)
    self.place(done)
    self.mstore("int", "0", sa)
    self.gen_stop()
    self.place(end)
    return r


def binds(n: Node, x: str, loop: bool) -> int:
    # how often code n binds name x as a local of its function: 2 where it may bind it again (in a
    # loop, a for loop's target, a global or nonlocal declaration), not counting the functions,
    # lambdas, classes and comprehensions it defines (but a def's or class's own name)
    k = n.kind
    if k == "def" or k == "class" or k == "subclass":
        return (2 if loop else 1) if n.s == x else 0
    if k == "lambda" or k == "listcomp" or k == "setcomp" or k == "dictcomp" or k == "nestedcomp":
        return 0
    if (k == "global" or k == "nonlocal") and len([g for g in n.kids if g.s == x]) > 0:
        return 2
    tg: list[Node] = []
    if k == "assign":
        tg = n.kids[:-1]
    elif k == "annassign" or k == "augassign" or k == "for" or k == "walrus":
        tg = [n.kids[0]]
    elif k == "with":
        tg = [it.kids[1] for it in n.kids[:-1] if len(it.kids) == 2]
    elif k == "del":
        tg = n.kids
    names: list[str] = []
    for t in tg:
        names_in(t, names)
    c = len([nm for nm in names if nm == x])
    if (k == "except" and n.s == x) or (k == "import" and len([a for a in n.kids if a.s == x]) > 0):
        c += 1
    if c > 0 and (loop or k == "for"):
        return 2
    for kid in n.kids:
        c += binds(kid, x, loop or k == "for" or k == "while")
        if c > 1:
            return 2
    return c


def maybe_unbound(n: Node, x: str) -> bool:
    # does code n read x where Flow found it may be unassigned (Node.chk)
    if n.kind == "name" and n.s == x and n.chk:
        return True
    for k in n.kids:
        if maybe_unbound(k, x):
            return True
    return False


def gen_genexp_value(self, n: Node) -> Val:
    # a generator expression (e for t in it if c) as a value: an anonymous generator function, as
    # CPython's (never a list): it is evaluated here, the rest where the generator runs. The
    # variables of this function it reads are passed to it as they are now, which is what they
    # hold when it runs: each is a parameter never bound again or a local bound once (outside any
    # loop), surely assigned here; another (a comprehension's, one bound again) is an error
    line = n.line
    noann = mk("noann", "", line, [])
    body = comp_clauses(n, [mk("expr", "", line, [mk("yield", "", line, [n.kids[0]])])], False)
    # its first iterable: a value made here, or range(), enumerate(), zip() or reversed() of
    # arguments evaluated here (those are no values: the generator's loop makes them)
    first = n.kids[2]
    ps: list[Node] = [mk("param", ".0", line, [noann, noann])]
    itn = mk("name", ".0", line, [])
    if self.iterator_call(first):
        ps = []
        cargs: list[Node] = []
        for j in range(len(first.kids) - 1):
            a = first.kids[j + 1]
            ps.append(mk("param", f".{j}", line, [noann, noann]))
            cargs.append(mk("kw", a.s, line, [mk("name", f".{j}", line, [])]) if a.kind == "kw" else mk("name", f".{j}", line, []))
        itn = mk("call", "", line, [first.kids[0]] + cargs)
    loop = mk("for", "", line, [n.kids[1], itn, mk("block", "", line, body)])
    d = mk("def", "<genexpr>", line, [mk("params", "0,-1", line, ps), noann, mk("block", "", line, [loop])])
    free: dict[str, bool] = {}
    closure_free(d, free)
    f = self.curfn
    fbody = f.node.kids[2].kids if f.node.kind == "def" else f.node.kids
    caps: list[str] = []
    for x in free:
        if x in self.compvars:
            self.err(f"a generator expression that reads '{x}', a variable of a comprehension around it, is not supported (it would read the variable's last value when it runs)")
        if not self.modlevel and x in self.ltype and not (x in self.assigned or x in f.params):
            self.err(f"a generator expression that reads '{x}', a variable of a function around {short(f.name)}(), is not supported")
        if self.modlevel or not (x in self.assigned or x in f.params):
            continue  # (a global, read where the generator runs)
        nb = 0
        for st in fbody:
            nb += binds(st, x, False)
        if nb > (0 if x in f.params and x not in self.assigned else 1) or x in self.nlw or maybe_unbound(n, x):
            self.err(f"a generator expression that reads '{x}' is not supported where {short(f.name)}() may bind it again, or it may be unbound, before the generator runs (a generator expression reads it then)")
        caps.append(x)
    caps.sort()
    for x in caps:
        d.kids[0].kids.append(mk("param", x, line, [noann, noann]))
    firsts: list[Node] = []
    own: FnInfo | None = None
    if self.iterator_call(first):
        for a in first.kids[1:]:
            firsts.append(self.vnode(self.expr(a.kids[0] if a.kind == "kw" else a, "")))
    else:
        self.gencall = ""
        it = self.iterable(self.expr(first, ""))  # (made here)
        if self.owned_gen(it, first) > 0:
            own = self.gencallf  # (a generator it alone holds: its loop owns it)
        firsts.append(self.vnode(it))
    g = self.declare_fn(d, "")
    self.ngenexp += 1
    g.ll = f"@f.genexpr.{self.ngenexp}"
    g.mod = f.mod
    g.home = self.fn_home(f)  # (the identity policy of the code around it: dynamic.py)
    g.gfirst = own
    return self.call_fn(g, [], firsts + [mk("name", x, line, []) for x in caps])
