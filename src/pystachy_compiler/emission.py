"""Emission component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.utils import is_union, unionnames
from src.pystachy_compiler.bigints import narrows
from src.pystachy_compiler.diagnostics import ClassBoxes, Rejoin, fail, int_lists
from src.pystachy_compiler.names import short
from src.pystachy_compiler.ircheck import CONSTRAINT_PARTS, native_type, ref_type, value_view
from src.pystachy_compiler.ir import slot_register
from src.pystachy_compiler.specs import NONEVAR, OP_OPERAND_TYPES, OP_RESULT_TYPE, OP_TEMPS
from src.pystachy_compiler.frames import Frame
from src.pystachy_compiler.ir import Blk, Data, IFn, Ins, Val, tmpname, one_num, value_definitions
from src.pystachy_compiler.specs import BIGOPT, CHECKED, EMPTYFS, LIST_READS, LIST_WRITES, NARROWED, PATH_OPS, RTL, RTSYM, STR_HEADER_SIZE, TEXT_OPS
from src.pystachy_compiler.unions import FLOATAT, MEMBERAT
from src.pystachy_compiler.utils import (
    RT_VARS,
    RtFn,
    elem,
    identity_abi,
    is_fset,
    is_opt,
    is_sopt,
    is_tuple,
    is_vtuple,
    list_read_error,
    list_write_error,
    numeric_identity,
    optnames,
    runtime_decl,
    rt_bind,
    rt_generic,
    rt_open,
    rt_operand_order,
    rt_subst,
    rt_words,
    rtsym,
    same_kind,
    selem,
    targs,
    typestr,
    unopt,
)


def gen_err(self, msg: str) -> None:
    if self.xtry != "":
        # A comparison specialization may decline on the next pass. An unsupported
        # iteration protocol instead gets an explicit runtime-error arm; unused
        # methods must not make an otherwise accepted program fail to compile.
        self.newx[self.xtry] = True
        if self.xtry.startswith("narrow:"):
            # (nor may a declined narrowing's union type storage on the next pass: this pass's
            # joins are found again where they are not its, see narrows)
            self.newhints = {}
        raise Rejoin()
    if len(self.newhints) > 0 and not self.final:
        raise Rejoin()  # (an error after a join may come of the narrower type it widens: see Rejoin)
    if len(self.clsused) > 0:
        # (it may come of a class read as a typed class object where a module that opts in to
        # dynamic Any, and names no type[C], made a class box of it before: compiled again so,
        # see ClassBoxes, which then retries a hierarchy or a narrowing below as before)
        raise ClassBoxes()
    self.retry_hierarchy(msg)
    if len(self.ncand) > 0 and self.curfn is not None:
        # (an error that no join or hierarchy explains, in a function whose isinstance() tests of
        # class tuples narrowed nothing (see narrows): the next pass narrows them, as the error
        # may come of x's base type there; an error in that pass declines them, above, and this
        # pass's error is reported then)
        key = f"narrow:{self.fnkey(self.curfn)}:"
        want = [c for c in self.ncand if c.startswith(key) and c not in self.xwant and c not in self.xnot]
        if len(want) > 0:
            for c in want:
                self.newwant[c] = True
            raise Rejoin()
    if len(self.making) > 0:
        # an error in a template's function: say which call made it compile
        for i in range(len(self.making) - 1, -1, -1):
            msg += ("; " if i < len(self.making) - 1 else " (") + self.making[i]
        msg += ")"
    if FLOATAT in self.hints:
        # (an error of a pass after a join of a location annotated float, which may come of the
        # union it holds now: float_takes)
        msg += f" (note: what is annotated float and was given an int at {self.hints[FLOATAT]} holds an int | float; a float there, as in 1.0 or float(x), keeps it a float)"
    if MEMBERAT in self.hints:
        # (and of one annotated int or str, given an enum member: ann_takes)
        at = self.hints[MEMBERAT].split("|")
        kept = "an int" if at[1] == "int" else "a str"
        msg += f" (note: what is annotated {at[1]} and was given a member of {short(at[2])} at {at[0]} holds {at[1]} | {short(at[2])}, as CPython's does; its .value there keeps it {kept})"
    if "opt[" in msg or "union[" in msg:
        msg = optnames(unionnames(msg))
    for name in self.recursive:
        # (a recursive alias's edge is the alias, as typestr writes it; the message may quote the
        # program's text, getattr(o, "rec[1]"), which only an alias's own name could match)
        msg = msg.replace("rec[" + name + "]", short(name))
    fail(msg, self.line, self.making)

def gen_save(self) -> Frame:
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
    fr.lcsoft = self.lcsoft
    fr.ret = self.ret
    fr.retann = self.retann
    fr.nn = self.nn
    fr.dynints = self.dynints
    fr.selfname = self.selfname
    fr.uflags = self.uflags
    fr.lflag = self.lflag
    fr.iflag = self.iflag
    fr.appends = self.appends
    fr.owned = self.owned
    fr.idbox = self.idbox
    fr.idstores = self.idstores
    fr.cells = self.cells
    fr.nlw = self.nlw
    fr.nonevars = self.nonevars
    fr.nonesites = self.nonesites
    fr.nonepending = self.nonepending
    fr.narrowed = self.narrowed
    fr.preadn = self.preadn
    fr.preadv = self.preadv
    fr.preads = self.preads
    fr.preadb = self.preadb
    fr.pdoms = self.pdoms
    fr.psess = self.psess
    fr.pfield = self.pfield
    fr.lkk = self.lkk
    fr.branch = self.branch
    fr.modlevel = self.modlevel
    fr.lenient = self.lenient
    fr.drying = self.drying
    fr.carried = self.carried
    fr.nonecmp = self.nonecmp
    fr.fieldcmp = self.fieldcmp
    fr.rolex = self.rolex
    fr.cmpnode = self.cmpnode
    fr.stkkey = self.stkkey
    fr.reflcopies = self.reflcopies
    fr.stmtexpr = self.stmtexpr
    fr.dmemo = self.dmemo
    fr.dmemot = self.dmemot
    fr.n = self.n
    fr.cur = self.cur
    fr.term = self.term
    fr.line = self.line
    return fr

def gen_restore(self, fr: Frame) -> None:
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
    self.lcsoft = fr.lcsoft
    self.ret = fr.ret
    self.retann = fr.retann
    self.nn = fr.nn
    self.dynints = fr.dynints
    self.selfname = fr.selfname
    self.uflags = fr.uflags
    self.lflag = fr.lflag
    self.iflag = fr.iflag
    self.appends = fr.appends
    self.owned = fr.owned
    self.idbox = fr.idbox
    self.idstores = fr.idstores
    self.cells = fr.cells
    self.nlw = fr.nlw
    self.nonevars = fr.nonevars
    self.nonesites = fr.nonesites
    self.nonepending = fr.nonepending
    self.narrowed = fr.narrowed
    self.preadn = fr.preadn
    self.preadv = fr.preadv
    self.preads = fr.preads
    self.preadb = fr.preadb
    self.pdoms = fr.pdoms
    self.psess = fr.psess
    self.pfield = fr.pfield
    self.lkk = fr.lkk
    self.branch = fr.branch
    self.modlevel = fr.modlevel
    self.lenient = fr.lenient
    self.drying = fr.drying
    self.carried = fr.carried
    self.nonecmp = fr.nonecmp
    self.fieldcmp = fr.fieldcmp
    self.rolex = fr.rolex
    self.cmpnode = fr.cmpnode
    self.stkkey = fr.stkkey
    self.reflcopies = fr.reflcopies
    self.stmtexpr = fr.stmtexpr
    self.dmemo = fr.dmemo
    self.dmemot = fr.dmemot
    self.n = fr.n
    self.cur = fr.cur
    self.term = fr.term
    self.line = fr.line

def gen_tmp(self) -> str:
    self.n += 1
    return tmpname(self.n)

def gen_label(self) -> str:
    self.n += 1
    return f"L{self.n}"


def gen_add(self, i: Ins) -> None:
    # code after a terminator (dead code) goes to a block of its own. i takes the line being
    # compiled (Ins.line), as jump's branch and slot's entry storage do
    if self.term:
        self.place(self.label())
    i.line = self.line
    if i.op in PATH_OPS:
        self.path_event(i, PATH_OPS[i.op])  # (what a narrowed attribute path's facts do not outlast: unions.py)
    self.blk.code.append(i)

def gen_put(self, i: Ins, k: int) -> None:
    # add i, which defines k values, numbered as k separate instructions would have been (one
    # value: the shared list of its number, one_num, which nothing appends to)
    self.n += 1
    i.r = one_num(self.n) if k == 1 else [self.n]
    self.add(i)
    for _ in range(k - 1):
        self.n += 1
        i.r.append(self.n)


def gen_mem_load(self, a: Val) -> Val:
    # Read a native value through its typed address &T. LLVM alone selects its spelling.
    if not a.t.startswith("&"):
        fail(f"internal error: mem.load through {a.v} of type {a.t}, which is no address", 0)
    i = Ins("mem.load", a.t[1:], "")
    i.a = [a]
    self.put(i, 1)
    return Val(tmpname(i.r[0]), i.t)

def gen_mem_store(self, a: Val, v: Val) -> None:
    if not a.t.startswith("&"):
        fail(f"internal error: mem.store through {a.v} of type {a.t}, which is no address", 0)
    i = Ins("mem.store", "", "")
    i.a = [a, v]
    self.add(i)

def gen_place(self, l: str) -> None:
    if not self.term:
        self.jump(l)
    self.blk = Blk(l)
    self.blk.handler = self.handler
    self.fn.blocks.append(self.blk)
    self.cur = l
    self.term = False

def gen_jump(self, l: str) -> None:
    i = Ins("br", "", "")
    i.line = self.line
    i.b = [l]
    self.blk.code.append(i)

def gen_slot(self, i: Ins) -> None:
    # add slot op i to the function's entry storage, numbered by the caller: like any op, it takes
    # the line being compiled, which binds its variable first (a parameter's: the def's line)
    i.line = self.line
    self.fn.slots.append(i)

def gen_br(self, l: str) -> None:
    if not self.term:
        self.jump(l)
        self.term = True

def gen_cbr(self, c: str, a: str, b: str) -> None:
    i = Ins("cbr", "", "")
    i.a = [Val(c, "bool")]
    i.b = [a, b]
    self.add(i)
    self.term = True

def gen_switch(self, v: Val, cases: list[str], to: list[str], other: str) -> None:
    # go to to[j] where int v is cases[j], distinct int literals, else to other
    i = Ins("switch", "", "")
    i.a = [v] + [Val(c, "int") for c in cases]
    i.b = [other] + to
    self.add(i)
    self.term = True

def gen_ret_(self, v: Val) -> None:
    # return v (of type None: return nothing)
    if identity_abi(self.curfn) and numeric_identity(v.t) and self.idhere():
        # Fresh arithmetic needs no box until its caller observes identity. An existing
        # binding/constant keeps its box, including the defining module's constant pool.
        b = Val(v.idfrom, "dyn") if v.idfrom != "" else self.dyn_id_held(v) if v.idslot != "" else self.dyn_id_box(v) if v.lit or v.t not in ["int", "int+", "float"] else Val("null", "dyn")
        self.mem_store(Val("%idret", "&dyn"), b)
    i = Ins("ret", "", "")
    if v.t != "None":
        i.a = [v]
    self.add(i)
    self.term = True

def gen_returned_none(self) -> bool:
    # has the template's function being compiled returned None before it was known what it
    # returns (a ret.none op)
    for b in self.fn.blocks:
        for x in b.code:
            if x.op == "ret.none":
                return True
    return False

def gen_unreachable(self) -> None:
    self.add(Ins("unreachable", "", ""))
    self.term = True

def gen_incoming(self, ph: Ins, v: str, l: str) -> None:
    # the value v of phi ph when control comes from block l
    if len(ph.b) == 0:
        ph.a = []
        ph.b = []
    ph.a.append(Val(v, ph.t))
    ph.b.append(l)

def gen_phi(self, ph: Ins) -> str:
    self.put(ph, 1)
    return tmpname(ph.r[0])

def gen_select(self, c: str, x: Val, y: Val) -> str:
    # c ? x : y, where x and y have the same type
    i = Ins("select", x.t, "")
    i.a = [Val(c, "bool"), x, y]
    self.put(i, 1)
    return tmpname(i.r[0])

def gen_cast(self, v: Val, t: str, kind: str) -> Val:
    # v read as a t: a cast op of kind (specs.CAST_KINDS), which lowering erases, so that its uses
    # read v (Gen.erase_casts). Until its function is complete it is numbered below zero, by a
    # count that only needs to tell casts apart (no frame keeps it, and dry() may use numbers
    # it drops); number_casts then numbers the function's casts after its last value, so that
    # no other value's number, and so no LLVM name, changes
    self.ncasts += 1
    i = Ins("cast", t, kind)
    i.a = [v]
    i.r = one_num(-self.ncasts)
    self.add(i)
    return Val(tmpname(-self.ncasts), t)

def gen_number_casts(self) -> None:
    # number the casts of the function being completed (gen_cast) after its last value, in the
    # order of its blocks, and name them so in their operands and in its loops' values
    names: dict[str, str] = {}
    for b in self.fn.blocks:
        for i in b.code:
            if i.op == "cast" and len(i.r) == 1 and i.r[0] < 0:
                self.n += 1
                names[tmpname(i.r[0])] = tmpname(self.n)
                i.r = one_num(self.n)
                self.fn.casts.append(self.n)
    if len(names) == 0:
        return
    for b in self.fn.blocks:
        for i in b.code:
            for a in i.a:
                if a.v in names:
                    a.v = names[a.v]
    for lp in self.fn.loops:
        for v in [lp.stop] + lp.seqs:
            if v.v in names:
                v.v = names[v.v]
        for k in range(len(lp.idx)):
            if lp.idx[k] in names:
                lp.idx[k] = names[lp.idx[k]]

def gen_rt(self, name: str, ret: str, args: list[str], x: str = "", t: str = "") -> str:
    # an rt op: a call of runtime function name (its LLVM symbol), whose LLVM result type is
    # ret, with args "<LLVM type> <value>", which must be what its RUNTIME entry says. (In
    # runtime mode, a function that runtime.py defines is called the same way: it is defined,
    # not declared, with RUNTIME's types, which Gen.function checks.) x: the descriptor of the
    # keys a dict or set op hashes (key_fx), for its U?; t: its result's type, where that holds a
    # type variable that no operand binds (a new list's items): an instance of its signature's.
    # Its operands have the signature's types until Gen.instantiate gives them their values'.
    if not self.rtmode:
        if name == "pys_chr":
            name = "pys_text_chr"
        elif name in TEXT_OPS:
            name = TEXT_OPS[name]
    if self.rtmode and "@" + name == self.curfn.ll:
        self.err(f"{name}() implements an operation that it uses: write it without that operation")
    k = self.runtime(name)
    ts = self.rtfns[k].sig
    ll = self.rtfns[k].ll
    if k == "setrecursionlimit":
        self.fn.setslimit = True  # (it compares the depth word with the new limit: Gen.recursionscope)
    if k in NARROWED and int_lists():
        # (a list of ints that may hold promoting ints past 64 bits, which it reads as 64-bit ints,
        # and the dict whose values it reads so)
        for j in range(min(len(args), len(ts) - 1)):
            if ts[j + 1].startswith("list["):
                self.rt("pys_list_narrow", "void", [args[j]])
            elif ts[j + 1] == "S" and k.startswith("dict."):
                self.rt("pys_dict_narrow", "void", [args[j]])
    ok = ret == ll[0] and len(args) == len(ll) - 1
    if t != "" and not rt_bind(ts[0], t, {}, True):
        fail(f"internal error: {name} given the result type {t}, which is no instance of {ts[0]}", 0)
    i = Ins("rt", ts[0] if t == "" else t, k)
    i.a = []
    i.x = x
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
        fail(f"internal error: {name} called as {ret} ({', '.join(args)}), but RUNTIME declares it as {runtime_decl(k)}", 0)
    if k in LIST_READS:
        fail(f"internal error: {k} needs list_get's concrete storage operands", 0)
    if k in LIST_WRITES:
        fail(f"internal error: {k} needs list_write's concrete storage operands", 0)
    if ret == "void":
        self.add(i)
        return ""
    self.put(i, 1)
    result = tmpname(i.r[0])
    # Native producers of fresh numeric lists have no source boxes to preserve.
    # Establish their item objects before a later copy can alias those objects.
    if self.list_id_kind(ts[0]) != 0:
        self.list_identity(Val(result, ts[0]))
    return result


def gen_instantiate(self, fn: IFn) -> None:
    # Type the runtime calls of fn, once it is built, by what they work on, as a call of a generic
    # function instantiates its signature (docs/typed-ir.md#runtime-calls): the type variables of
    # each rt op's signature (RT_VARS: S its receiver, T, K and V what that holds, U a second
    # value's, R a result's) bind to the result type its builder gave it (gen_rt's t) and to the
    # types of the values its operands read, the receiver's last (instantiate_op). The verifier
    # checks that each op is then an instance of its signature (rt_instance_error). A variable is
    # told from a class of its name (class T) by where it is: the signature's type that the
    # builder left. An op may read a result that a later op defines (where a loop brings it
    # back): another round types it once a round typed that result. Each round costs a pass over
    # fn, so three bound the work; an operand still pending keeps its variables (instance view).
    types: dict[str, str] = {}
    makers: dict[str, str] = {}
    pending: dict[str, bool] = {}  # (results whose type is their signature's, which names a variable)
    found = False
    again = True
    rounds = 0
    while again and rounds < 3:
        again = False
        lates: list[str] = []  # (the pending values that this round's ops read)
        rounds += 1
        for b in fn.blocks:
            for i in b.code:
                if i.op != "rt" or i.s not in self.rtfns or not self.rtfns[i.s].generic:
                    continue
                if not found:
                    value_definitions(fn, types, makers)
                    for c in fn.blocks:
                        for x in c.code:
                            if x.op == "rt" and len(x.r) > 0 and x.s in self.rtfns and x.t == self.rtfns[x.s].sig[0] and rt_generic(x.t):
                                pending[tmpname(x.r[0])] = True
                    found = True
                if instantiate_op(i, self.rtfns[i.s].sig, types, pending, lates) and len(i.r) > 0:
                    name = tmpname(i.r[0])
                    types[name] = i.t
                    if name in pending:
                        pending.pop(name)
        for v in lates:
            if v not in pending:
                again = True  # (a value an op read too late has its type now)


def makes_hole(i: Ins) -> bool:
    # does op i make an empty list, dict or set whose type a later use decides (Gen.hole): the
    # type that use gives its hole (Gen.holes) is its result's
    return i.op == "rt" and (i.s == "list.new" or i.s == "dict.new" or i.s == "set.new")


def open_type(t: str, rt: bool, classes: dict[str, bool]) -> bool:
    # does type t leave a part open: an empty container's placeholder (?), or a runtime type
    # variable (RT_VARS) that names no class or, in an rt op's result (rt), any
    if "?" in t:
        return True
    if not rt_generic(t):
        return False
    for w in rt_words(t):
        if w in RT_VARS and (rt or w not in classes):
            return True
    return False


def fills(pattern: str, t: str, rt: bool, classes: dict[str, bool]) -> bool:
    # is type t, which leaves no part open (open_type: a variable's name in t is a class's),
    # pattern with a type in each open part (rt: as an rt op's result type leaves them)
    if open_type(t, False, classes) or t == "" or t.startswith("%"):
        return False
    if pattern == t:
        return True
    if pattern == "?" or (pattern in RT_VARS and (rt or pattern not in classes)):
        return True
    if pattern[:1] == "*" or pattern[:1] == "&":
        return t[:1] == pattern[:1] and fills(pattern[1:], t[1:], rt, classes)
    h = pattern.find("[")
    if h <= 0 or not pattern.endswith("]") or not t.startswith(pattern[: h + 1]) or not t.endswith("]"):
        return False
    xs = targs(pattern)
    ys = targs(t)
    if len(xs) != len(ys):
        return False
    for j in range(len(xs)):
        if not fills(xs[j], ys[j], rt, classes):
            return False
    return True


def tie_part(i: Ins, j: int) -> list[str]:
    # the parts (ircheck.constraint_parts) of the constraint that the types column of op i's row
    # puts on its operand j (on its result where j < 0), or [] where the row puts none
    if i.op not in OP_OPERAND_TYPES:
        return []
    if j < 0:
        return CONSTRAINT_PARTS[OP_RESULT_TYPE[i.op]] if OP_RESULT_TYPE[i.op] != "" else []
    cs = OP_OPERAND_TYPES[i.op]
    if len(cs) == 0:
        return []
    return CONSTRAINT_PARTS[cs[j] if j < len(cs) else cs[len(cs) - 1]]


def retyped(a: Val, t: str) -> Val:
    # operand a, read at type t
    x = Val(a.v, t)
    x.identity(a)
    x.lit = a.lit
    x.infer_from = a.infer_from
    return x


class Settling:
    # Gen.settle of one function: each value's type and what defines it (ir.value_definitions),
    # the op or slot that does, the ops that read it, the values whose types changed and whose
    # operands are still to follow them, and the open values still to decide
    def __init__(self, fn: IFn, holes: list[str], classes: dict[str, bool], rtfns: dict[str, RtFn], late: bool):
        self.fn = fn
        self.rtfns = rtfns
        self.holes = holes
        self.classes = classes
        self.late = late
        # (only the values whose definitions leave their types open, as ir.value_definitions types
        # them: no other value's type changes, nor is read here. A placeholder's, and once
        # Gen.instantiate has run an rt op's result's variable: a value another op copies one to
        # keeps it, as the instance view reads it)
        self.types: dict[str, str] = {}
        self.makers: dict[str, str] = {}
        self.defs: dict[str, Ins] = {}
        self.readers: dict[str, list[Ins]] = {}
        for i in fn.slots:
            if "?" in i.t:
                reg = slot_register(i)
                self.types[reg] = i.t if i.k == 2 else "&" + i.t
                self.makers[reg] = "slot"
                self.defs[reg] = i
        for b in fn.blocks:
            for i in b.code:
                if len(i.r) > 0 and ("?" in i.t or (late and i.op == "rt" and rt_generic(i.t))):
                    named: list[int] = []
                    for j in range(len(i.r)):
                        if not (i.op in OP_TEMPS and j in OP_TEMPS[i.op]):
                            named.append(i.r[j])
                    if len(named) == 1:
                        v = tmpname(named[0])
                        self.types[v] = i.t
                        self.makers[v] = i.op
                        self.defs[v] = i
        for b in fn.blocks:
            for i in b.code:
                for a in i.a:
                    if a.v in self.defs:
                        if a.v not in self.readers:
                            self.readers[a.v] = []
                        if len(self.readers[a.v]) == 0 or self.readers[a.v][len(self.readers[a.v]) - 1] is not i:
                            self.readers[a.v].append(i)
        self.follow: list[str] = []

    def rt(self, v: str) -> bool:
        return self.makers[v] == "rt"

    def unsettled(self, v: str) -> bool:
        # is v's type open where this settling may decide it: not a local's first None (whose
        # slot keeps NONEVAR: specs.TYPE_VIEWS' instance), nor, before Gen.instantiate, an rt
        # op's result whose type is still its signature's
        d = self.types[v]
        if NONEVAR in d or v not in self.defs or not open_type(d, self.rt(v), self.classes):
            return False
        return self.late or "?" in d or not self.rt(v)

    def hole(self, i: Ins, d: str, tries: list[str]) -> None:
        # the type that a use gave the hole of op i (Gen.holes), which makes or reads a value of
        # type d, as the first of tries
        if i.k > 0 and i.k < len(self.holes):
            h = self.holes[i.k]
            if h != "" and same_kind(h, d) and h not in tries:
                tries.append(h)

    def define(self, v: str, t: str) -> None:
        # give v type t where it is defined, and the positions of its op that bind it so
        self.types[v] = t
        i = self.defs[v]
        if self.makers[v] == "slot":
            i.t = t if i.k == 2 else t[1:]
        else:
            i.t = t
            self.tie(i, -1, t)
        self.follow.append(v)

    def operand(self, i: Ins, j: int, t: str) -> None:
        # op i reads its operand j at type t, and the positions that bind it so take what t gives
        i.a[j] = retyped(i.a[j], t)
        self.tie(i, j, t)

    def tie(self, i: Ins, j: int, t: str) -> None:
        # The positions of op i that its row's types column binds by the variable that position j
        # binds (mem.load's &$T and $T), now that j has type t: each that leaves open what t
        # gives it takes that. An rt op's are its runtime signature's (tie_rt)
        if i.op == "rt":
            self.tie_rt(i)
            return
        p = tie_part(i, j)
        if len(p) == 0 or p[1] == "" or len(t) <= len(p[0]) + len(p[3]) or not t.startswith(p[0]) or not t.endswith(p[3]):
            return
        bound = t[len(p[0]) : len(t) - len(p[3])]
        for k in range(len(i.a)):
            q = tie_part(i, k)
            if k != j and len(q) > 0 and q[1] == p[1]:
                want = q[0] + bound + q[3]
                if i.a[k].t != want and open_type(i.a[k].t, i.op == "rt", self.classes) and fills(i.a[k].t, want, i.op == "rt", self.classes):
                    self.operand(i, k, want)
        q = tie_part(i, -1)
        if j >= 0 and len(q) > 0 and q[1] == p[1]:
            want = q[0] + bound + q[3]
            for n in i.r:
                v = tmpname(n)
                if v in self.defs and self.defs[v] is i and self.types[v] == i.t and i.t != want and open_type(i.t, i.op == "rt", self.classes) and fills(i.t, want, i.op == "rt", self.classes):
                    self.define(v, want)

    def tie_rt(self, i: Ins) -> None:
        # The variables of rt op i's runtime signature (RT_VARS), bound as Gen.instantiate binds
        # them (instantiate_op) by its result and its operands whose types leave nothing open,
        # the receiver's last (rt_bind), give each operand and the result whose type leaves open
        # what they make it that type (a [None] list's None, *opt[?], once the list is a
        # list[opt[str]]); one that still has the signature's own type is instantiate's
        if i.s not in self.rtfns or not self.rtfns[i.s].generic:
            return
        sig = self.rtfns[i.s].sig
        n = min(len(i.a), len(sig) - 1)
        bound: dict[str, str] = {}
        if i.t != sig[0] and not i.t.startswith("%") and not open_type(i.t, True, self.classes):
            rt_bind(sig[0], i.t, bound, False)
        for j in rt_operand_order(sig):
            if j <= n:
                u = i.a[j - 1].t
                if u != sig[j] and not u.startswith("%") and not open_type(u, True, self.classes):
                    rt_bind(sig[j], u, bound, False)
        for j in range(n):
            s = sig[j + 1]
            a = i.a[j]
            if not rt_generic(s) or rt_open(s, bound):
                continue
            want = rt_subst(s, bound)
            if a.t != want and "?" in a.t and fills(a.t, want, True, self.classes):
                self.operand(i, j, want)
        if len(i.r) > 0 and rt_generic(sig[0]) and not rt_open(sig[0], bound) and "?" in i.t:
            want = rt_subst(sig[0], bound)
            v = tmpname(i.r[0])
            if i.t != want and v in self.defs and fills(i.t, want, True, self.classes):
                self.define(v, want)


def settle_decide(self, s: Settling, v: str) -> str:
    # The one type that v's open type leaves to give it, or "" for none: the type that the
    # use which decided an empty container's hole gave it (Gen.holes), where that is the
    # container's op, else that of the first operand that reads v at a type which leaves
    # nothing open and is more than a machine word, but a runtime signature's operand. Each
    # other such operand must read it at that type or by a view (ircheck.value_view): the
    # runtime reads a bytes as a str
    d = s.types[v]
    rt = s.rt(v)
    reads: list[str] = []
    by_rt: list[bool] = []
    tries: list[str] = []
    i = s.defs[v]
    if makes_hole(i):
        s.hole(i, d, tries)
    for r in s.readers.get(v, []):
        if r.op == "empty.kind":
            s.hole(r, d, tries)  # (what a template's call returns: Gen.typed_empty)
        for a in r.a:
            if a.v == v and not a.t.startswith("%") and not open_type(a.t, r.op == "rt", s.classes):
                reads.append(a.t)
                by_rt.append(r.op == "rt")
    for t in reads:
        if t not in tries:
            tries.append(t)
    for t in reads:
        if is_opt(t) and unopt(t) not in tries:
            tries.append(unopt(t))  # (an operand that reads it as opt[T]: optional's view)
    for t in tries:
        if not fills(d, t, rt, s.classes):
            continue
        ok = True
        for j in range(len(reads)):
            if reads[j] != t and value_view(self, t, reads[j], rt, by_rt[j]) == "":
                ok = False
                break
        if ok:
            return t
    return ""


def settle_run(self, s: Settling) -> None:
    # decide the open values until none is left that a round can decide, each round after
    # the operands that read the values it gave types follow them
    pending: list[str] = []
    for v in s.types:
        if s.unsettled(v):
            pending.append(v)
    progress = True
    while progress:
        while len(s.follow) > 0:
            v = s.follow.pop()
            t = s.types[v]
            for r in s.readers.get(v, []):
                for j in range(len(r.a)):
                    a = r.a[j]
                    if a.v == v and a.t != t and open_type(a.t, r.op == "rt", s.classes) and fills(a.t, t, r.op == "rt", s.classes):
                        s.operand(r, j, t)
        progress = False
        rest: list[str] = []
        for v in pending:
            if not s.unsettled(v):
                continue
            t = settle_decide(self, s, v)
            if t == "" or t == s.types[v]:
                rest.append(v)  # (or a class's name that an rt op's variable spells)
            else:
                s.define(v, t)
                progress = True
        pending = rest


def words_cast(self, fn: IFn, words: dict[str, str]) -> None:
    # A bits cast for each type an operand reads an rt op's machine word at (words: each rt op's
    # result of %ptr or %slot, as RUNTIME gives it): the cast reads the word as that type, right
    # after the op, and the operands read the cast (gen_cast: lowering erases it). A runtime
    # signature's operand of a type variable reads the word itself, as the runtime does; a type
    # that no bits cast reads a word as is left to the verifier.
    casts: dict[str, dict[str, str]] = {}
    after: dict[str, list[Ins]] = {}
    for b in fn.blocks:
        for i in b.code:
            for j in range(len(i.a)):
                a = i.a[j]
                if a.v not in words:
                    continue
                d = words[a.v]
                u = a.t
                if u.startswith("%") or (i.op == "rt" and rt_generic(u)):
                    continue
                if not ((d == "%ptr" and (ref_type(u) or (u.startswith("&") and native_type(u[1:], self.classes)))) or (d == "%slot" and (u == "int" or (u.startswith("*") and native_type(u[1:], self.classes))))):
                    continue
                if a.v not in casts:
                    casts[a.v] = {}
                if u not in casts[a.v]:
                    c = Ins("cast", u, "bits")
                    c.a = [Val(a.v, d)]
                    self.n += 1
                    c.r = one_num(self.n)
                    fn.casts.append(self.n)
                    casts[a.v][u] = tmpname(self.n)
                    if a.v not in after:
                        after[a.v] = []
                    after[a.v].append(c)
                i.a[j] = retyped(a, u)
                i.a[j].v = casts[a.v][u]
    if len(after) == 0:
        return
    for lp in fn.loops:
        # (a loop record's values, as its operands read them: new Vals, as another op may hold these)
        if lp.stop.v in casts and lp.stop.t in casts[lp.stop.v]:
            lp.stop = Val(casts[lp.stop.v][lp.stop.t], lp.stop.t)
        for k in range(len(lp.seqs)):
            x = lp.seqs[k]
            if x.v in casts and x.t in casts[x.v]:
                lp.seqs[k] = Val(casts[x.v][x.t], x.t)
    for b in fn.blocks:
        code: list[Ins] = []
        for i in b.code:
            code.append(i)
            if len(i.r) > 0 and i.op == "rt" and tmpname(i.r[0]) in after:
                for c in after[tmpname(i.r[0])]:
                    c.line = i.line
                    code.append(c)
        b.code = code


def gen_settle(self, fn: IFn, late: bool) -> None:
    # Give each value of fn, once it is built, one type (docs/typed-ir.md#operation-reference), as an MLIR
    # value has one: an open type (open_type) the frontend gave it before a later use decided
    # it, an empty container's placeholder (list[?]: Gen.hole) or a runtime type variable that
    # Gen.instantiate bound to nothing, takes the one type its uses read it at (Settling), and,
    # once instantiate has run (late), an rt op's machine word that an operand reads as a typed
    # value is read through a bits cast (words_cast). Before instantiate, the rt ops' operands
    # bind their variables to what is decided here: the values that empty containers hold. Most
    # functions hold neither, which one look at their ops' types tells
    open_ = False
    words: dict[str, str] = {}
    for i in fn.slots:
        if "?" in i.t:
            open_ = True
    for b in fn.blocks:
        for i in b.code:
            if "?" in i.t:
                open_ = True
            elif late and i.op == "rt" and len(i.r) > 0:
                if i.t == "%ptr" or i.t == "%slot":
                    words[tmpname(i.r[0])] = i.t
                elif rt_generic(i.t):
                    open_ = True
    if open_:
        classes: dict[str, bool] = {}
        for c in self.classes:
            classes[c] = True
        settle_run(self, Settling(fn, self.holes, classes, self.rtfns, late))
    if len(words) > 0:
        words_cast(self, fn, words)


def instantiate_op(i: Ins, sig: list[str], types: dict[str, str], pending: dict[str, bool], lates: list[str]) -> bool:
    # Gen.instantiate of rt op i, whose runtime function's signature is sig, in a function whose
    # values have types, but those that pending holds, whose types are still their signatures':
    # its type variables bind to its result's type where its builder gave one (not the
    # signature's), then to its operands' (rt_bind): the others', then the receiver's, as the
    # verifier binds them (rt_instance_error). An operand's type is the one its builder gave it
    # where that is not the signature's (a list op's), else its value's, as a receiver's that of
    # the value an optional holds (a runtime function's receiver is never None). Each operand
    # and the result whose builder left them the signature's types get them with the variables
    # replaced (rt_subst), but an operand that reads a value that claims no type (%slot, %ptr)
    # has that type. The builder's result type binds first, so that no operand overrides it (the
    # verifier binds the result last, to check it). Returns whether it retyped the result; the
    # pending values its operands read go to lates.
    bound: dict[str, str] = {}
    n = min(len(i.a), len(sig) - 1)
    if i.t != sig[0]:
        rt_bind(sig[0], i.t, bound, False)
    found: list[str] = []
    for j in range(n):
        s = sig[j + 1]
        a = i.a[j]
        t = ""
        if rt_generic(s):
            if a.t != s:
                t = a.t
            elif a.v in pending:
                lates.append(a.v)
            elif a.v in types:
                t = unopt(types[a.v]) if s == "S" else types[a.v]
        found.append(t)
    for j in rt_operand_order(sig):
        if j <= n and found[j - 1] != "":
            rt_bind(sig[j], found[j - 1], bound, False)
    for j in range(n):
        s = sig[j + 1]
        a = i.a[j]
        if a.t != s or not rt_generic(s):
            continue
        t = rt_subst(s, bound)
        d = found[j]
        if (d == "%slot" and s.startswith("*")) or (d == "%ptr" and not s.startswith("*")):
            t = d
        if t != a.t:
            i.a[j] = Val(a.v, t)
    if i.t == sig[0] and rt_generic(sig[0]):
        t = rt_subst(sig[0], bound)
        if t != i.t:
            i.t = t
            return True
    return False


def gen_list_len(self, o: Val) -> str:
    # The semantic owner survives to the bounds pass; LLVM still emits one load.
    i = Ins("list.len", "int", "")
    i.a = [o]
    error = list_read_error(i)
    if error != "":
        fail(f"internal error: list.len: {error}", 0)
    self.put(i, 1)
    return tmpname(i.r[0])


def gen_list_get(self, key: str, args: list[Val]) -> str:
    # Preserve the concrete receiver and packed result independently of the ABI.
    i = Ins("rt", "*" + elem(args[0].t) if key == "list.get" and len(args) > 0 else "dyn", key)
    i.a = args
    error = list_read_error(i, self.rtfns[key].sig if key in self.rtfns else None)
    if error != "":
        fail(f"internal error: {key}: {error}", 0)
    name = rtsym(key)
    if self.rtmode and "@" + name == self.curfn.ll:
        self.err(f"{name}() implements an operation that it uses: write it without that operation")
    self.runtime(name)
    self.put(i, 1)
    return tmpname(i.r[0])


def gen_list_write(self, key: str, args: list[Val]) -> None:
    # Operands have already been evaluated and encoded by the caller, in Python
    # order. Preserve the original identity box alongside its packed payload.
    i = Ins("rt", "None", key)
    i.a = args
    error = list_write_error(i, int_lists(), self.rtfns[key].sig if key in self.rtfns else None)
    if error != "":
        fail(f"internal error: {key}: {error}", 0)
    name = rtsym(key)
    if self.rtmode and "@" + name == self.curfn.ll:
        self.err(f"{name}() implements an operation that it uses: write it without that operation")
    self.runtime(name)
    self.add(i)


def gen_alloc_fixed(self, t: str) -> Val:
    # A zeroed, GC-scanned class or fixed tuple: only lowering chooses its byte size, and the call
    # (lowering's alloc_call: pys_alloc, or with allocelide pys_new for an object that holds no
    # reference, which it declares; whether one does is known once the class's layout is final)
    if self.rtmode and self.curfn.ll == "@pys_alloc":
        self.err("pys_alloc() implements an operation that it uses: write it without that operation")
    self.runtime("pys_alloc")
    i = Ins("alloc.fixed", t, "")
    self.put(i, 1)
    return Val(tmpname(i.r[0]), t)

def gen_runtime(self, name: str) -> str:
    # declare runtime function name (its LLVM symbol) from its RUNTIME entry; its key
    if name not in RTSYM:
        fail(f"internal error: no RUNTIME entry for {name}", 0)
    k = RTSYM[name]
    if k not in self.rtfns:
        self.rtfns[k] = RtFn(k)
    return k

def gen_hole(self, kind: str) -> Ins:
    # a new list, dict or set (kind) whose type a later use decides: the op holds a new hole
    i = Ins("rt", "dict[?,?]" if kind == "dict" else f"{kind}[?]", f"{kind}.new")
    i.a = [Val("0", "int")]  # (a dict's key kind, a set's element kind: the hole's, when it is lowered)
    if kind == "dict":
        i.a.append(Val("0", "int"))
    i.k = len(self.holes)
    self.holes.append("")
    self.runtime(f"pys_{kind}_new")
    self.put(i, 1)
    return i

def gen_checked(self, op: str, a: str, b: str) -> list[str]:
    # [result, overflowed] of 64-bit a op b (op: + - *), from llvm.s<op>.with.overflow.i64
    self.runtime(f"llvm.{CHECKED[op]}.with.overflow.i64")
    i = Ins("ovf", "int", op)
    i.a = [Val(a, "int"), Val(b, "int")]
    self.put(i, 3)  # (the call's {i64, i1}, then the two extractvalues)
    return [tmpname(i.r[1]), tmpname(i.r[2])]

def gen_guard(self, bad: str, msg: str) -> None:
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

def gen_primitive(self, name: str, vals: list[Val]) -> Val:
    # runtime.py's _rt.<name>(...): see RTL
    if name not in RTL:
        self.err(f"_rt.{name} is not a runtime primitive")
    sig = RTL[name].split(":")
    if ",".join([v.t for v in vals]) != sig[0]:
        self.err(f"_rt.{name}() takes ({sig[0].replace(',', ', ')}), not ({', '.join([typestr(v.t) for v in vals])})")
    a = [v.v for v in vals]
    # (a str's length and bytes are tagged, and the length bounded, in runtime.py's module, which
    # defines the metadata: lib/_pystachy_bytearray.py's module has the same operations untagged)
    lenr = "length.range" if self.rtmode else ""
    lenw = "length" if self.rtmode else ""
    data = "bytes" if self.rtmode else ""
    if name == "wrap_add" or name == "wrap_sub" or name == "wrap_mul":
        return Val(self.scalar(name[5:], [Val(a[0], 'int'), Val(a[1], 'int')]), "int")
    if name == "udiv" or name == "urem":
        self.guard(self.num_cmp('==', Val(a[1], "int"), Val('0', "int")).v, "ZeroDivisionError: integer division or modulo by zero")
        return Val(self.scalar(name, [Val(a[0], 'int'), Val(a[1], 'int')]), "int")
    if name == "sdiv" or name == "srem":
        signed_divisor = vals[1]
        zero = self.num_cmp("==", signed_divisor, Val("0", "int"))
        self.guard(zero.v, "ZeroDivisionError: integer modulo by zero" if name == "srem" else "ZeroDivisionError: integer division or modulo by zero")
        neg_one = self.num_cmp("==", signed_divisor, Val("-1", "int"))
        if name == "sdiv":
            minimum = self.num_cmp("==", vals[0], Val("-9223372036854775808", "int"))
            self.guard(self.scalar("and", [minimum, neg_one]), "OverflowError: integer result does not fit in 64 bits")
        else:
            # LLVM srem is undefined for MIN / -1. Both 1 and -1 divide every input exactly.
            signed_divisor = Val(self.select(neg_one.v, Val("1", "int"), signed_divisor), "int")
        return Val(self.scalar(name, [vals[0], signed_divisor]), "int")
    if name == "ctlz":
        return Val(self.rt("llvm.ctlz.i64", "i64", [f"i64 {a[0]}", "i1 false"]), "int")
    if name == "ctpop":
        return Val(self.rt("llvm.ctpop.i64", "i64", [f"i64 {a[0]}"]), "int")
    if name == "mul_ovf":
        return Val(self.checked("*", a[0], a[1])[1], "bool")
    if name == "mul_hi":
        # the product in 128 bits, where it cannot wrap; LLVM makes it one widening multiply
        p = self.scalar('mul', [Val(self.scalar_cast('zext', Val(a[0], 'int'), '%i128'), '%i128'), Val(self.scalar_cast('zext', Val(a[1], 'int'), '%i128'), '%i128')])
        return Val(self.scalar_cast('trunc', Val(self.scalar('lshr', [Val(p, '%i128'), Val('64', '%i128')]), '%i128'), 'int'), "int")
    if name == "urem_wide" or name == "udiv_wide":
        # Divide the unsigned 128-bit hi:lo by d, returning the low word of the result.
        self.guard(self.num_cmp("==", vals[2], Val("0", "int")).v, "ZeroDivisionError: integer division or modulo by zero")
        hi = Val(self.scalar_cast("zext", vals[0], "%i128"), "%i128")
        shifted_hi = Val(self.scalar("shl", [hi, Val("64", "%i128")]), "%i128")
        lo = Val(self.scalar_cast("zext", vals[1], "%i128"), "%i128")
        dividend = Val(self.scalar("or", [shifted_hi, lo]), "%i128")
        divisor = Val(self.scalar_cast("zext", vals[2], "%i128"), "%i128")
        wide = Val(self.scalar(name[:4], [dividend, divisor]), "%i128")
        return Val(self.scalar_cast("trunc", wide, "int"), "int")
    if name == "float_bits":
        return Val(self.scalar_cast('bitcast', Val(a[0], 'float'), 'int'), "int")
    if name == "bits_float":
        return Val(self.scalar_cast('bitcast', Val(a[0], 'int'), 'float'), "float")
    if name == "fma":
        return Val(self.rt("llvm.fma.f64", "double", [f"double {a[0]}", f"double {a[1]}", f"double {a[2]}"]), "float")
    if name == "sqrt":
        return Val(self.rt("llvm.sqrt.f64", "double", [f"double {a[0]}"]), "float")
    if name == "fdiv":
        return Val(self.scalar('fdiv', [Val(a[0], 'float'), Val(a[1], 'float')]), "float")
    if name == "shl" or name == "lshr" or name == "ashr":
        # by n mod 64, as the hardware shifts (LLVM would make a larger shift poison)
        return Val(self.scalar(name, [Val(a[0], 'int'), Val(self.scalar('and', [Val(a[1], 'int'), Val('63', 'int')]), 'int')]), "int")
    if name == "str_done":
        return vals[0]
    if name == "null":
        return Val(self.scalar_cmp('eq', Val(a[0], '%ptr'), Val('null', '%ptr')), "bool")
    if name == "same":
        # same(a, i, b, j, n): within both, and n >= 0
        n0 = self.mload('int', a[0], lenr)
        n1 = self.mload('int', a[2], lenr)
        for p, lhs, rhs in [("<", a[4], "0"), (">", a[1], n0), (">", a[4], self.scalar('sub', [Val(n0, 'int'), Val(a[1], 'int')])),
                            (">", a[3], n1), (">", a[4], self.scalar('sub', [Val(n1, 'int'), Val(a[3], 'int')]))]:
            x = self.num_cmp(p, Val(lhs, "int"), Val(rhs, "int")) if p == "<" else self.int_ucmp(p, Val(lhs, "int"), Val(rhs, "int"))
            self.guard(x.v, "IndexError: compare out of range")
        p0 = self.maddr('%byte', a[0], f"{self.scalar('add', [Val(a[1], 'int'), Val(str(STR_HEADER_SIZE), 'int')])}")
        p1 = self.maddr('%byte', a[2], f"{self.scalar('add', [Val(a[3], 'int'), Val(str(STR_HEADER_SIZE), 'int')])}")
        return Val(self.scalar_cmp('eq', Val(self.rt('memcmp', 'i32', [f'ptr {p0}', f'ptr {p1}', f'i64 {a[4]}']), '%i32'), Val('0', '%i32')), "bool")
    if name == "find_byte":
        # find_byte(s, c, st, en): 0 <= st <= en <= len(s)
        n0 = self.mload('int', a[0], lenr)
        for lhs, rhs in [(a[3], n0), (a[2], a[3])]:
            self.guard(self.int_ucmp(">", Val(lhs, "int"), Val(rhs, "int")).v, "IndexError: search out of range")
        self.guard(self.int_ucmp('>', Val(a[1], "int"), Val('255', "int")).v, "ValueError: byte must be in range(0, 256)")
        p0 = self.maddr('%byte', a[0], f"{self.scalar('add', [Val(a[2], 'int'), Val(str(STR_HEADER_SIZE), 'int')])}")
        f = self.rt("memchr", "ptr", [f"ptr {p0}", f"i32 {self.scalar_cast('trunc', Val(a[1], 'int'), '%i32')}", f"i64 {self.scalar('sub', [Val(a[3], 'int'), Val(a[2], 'int')])}"])
        d = self.scalar('sub', [Val(self.scalar_cast('ptrtoint', Val(f, '%ptr'), 'int'), 'int'), Val(self.scalar_cast('ptrtoint', Val(a[0], '%ptr'), 'int'), 'int')])
        return Val(self.select(self.scalar_cmp('eq', Val(f, '%ptr'), Val('null', '%ptr')), Val('-1', 'int'), Val(self.scalar('sub', [Val(d, 'int'), Val(str(STR_HEADER_SIZE), 'int')]), 'int')), "int")
    if name == "find_sub":
        # find_sub(h, n, st, en): 0 <= st <= en <= len(h)
        n0 = self.mload('int', a[0], lenr)
        for lhs, rhs in [(a[3], n0), (a[2], a[3])]:
            self.guard(self.int_ucmp(">", Val(lhs, "int"), Val(rhs, "int")).v, "IndexError: search out of range")
        p0 = self.maddr('%byte', a[0], f"{self.scalar('add', [Val(a[2], 'int'), Val(str(STR_HEADER_SIZE), 'int')])}")
        p1 = self.maddr('%byte', a[1], str(STR_HEADER_SIZE))
        m = self.mload('int', a[1], lenr)
        f = self.rt("memmem", "ptr", [f"ptr {p0}", f"i64 {self.scalar('sub', [Val(a[3], 'int'), Val(a[2], 'int')])}", f"ptr {p1}", f"i64 {m}"])
        d = self.scalar('sub', [Val(self.scalar_cast('ptrtoint', Val(f, '%ptr'), 'int'), 'int'), Val(self.scalar_cast('ptrtoint', Val(a[0], '%ptr'), 'int'), 'int')])
        return Val(self.select(self.scalar_cmp('eq', Val(f, '%ptr'), Val('null', '%ptr')), Val('-1', 'int'), Val(self.scalar('sub', [Val(d, 'int'), Val(str(STR_HEADER_SIZE), 'int')]), 'int')), "int")
    if name == "fail":
        if not a[0].startswith("@s."):
            self.err("_rt.fail() takes the exception's name as a str literal")
        self.raise_(self.strvals[int(a[0][3:])], a[1])
        self.place(self.label())  # (not reached)
        return Val("null", "None")
    if name == "str_new":
        # a size the allocator cannot serve (negative, or past 2**63 with the header and NUL)
        # is CPython's MemoryError, as in runtime.c
        self.guard(self.int_ucmp('>', Val(a[0], "int"), Val(str(9223372036854775807 - STR_HEADER_SIZE - 1), "int")).v, "MemoryError: ")
        r = self.rt("pys_alloc_atomic", "ptr", [f"i64 {self.scalar('add', [Val(a[0], 'int'), Val(str(STR_HEADER_SIZE + 1), 'int')], 'nuw nsw')}"])  # zeroed: dict_hash, chars1 and NUL
        self.mstore('int', a[0], r, lenw)
        return Val(r, "str")
    # the others index a str: an unsigned compare with its length also rejects a negative index
    n = self.mload('int', a[0], lenr)
    if name == "copy":
        # copy(dst, at, src, lo, n): dst[at:at + n] = src[lo:lo + n], within both
        m = self.mload('int', a[2], lenr)
        for p, lhs, rhs in [("<", a[4], "0"), (">", a[1], n), (">", a[4], self.scalar('sub', [Val(n, 'int'), Val(a[1], 'int')])),
                            (">", a[3], m), (">", a[4], self.scalar('sub', [Val(m, 'int'), Val(a[3], 'int')]))]:
            x = self.num_cmp(p, Val(lhs, "int"), Val(rhs, "int")) if p == "<" else self.int_ucmp(p, Val(lhs, "int"), Val(rhs, "int"))
            self.guard(x.v, "IndexError: copy out of range")
        dst = self.maddr('%byte', a[0], f"{self.scalar('add', [Val(a[1], 'int'), Val(str(STR_HEADER_SIZE), 'int')])}")
        src = self.maddr('%byte', a[2], f"{self.scalar('add', [Val(a[3], 'int'), Val(str(STR_HEADER_SIZE), 'int')])}")
        self.rt("llvm.memmove.p0.p0.i64", "void", [f"ptr {dst}", f"ptr {src}", f"i64 {a[4]}", "i1 false"])
        return Val("null", "None")
    self.guard(self.int_ucmp('>=', Val(a[1], "int"), Val(n, "int")).v, "IndexError: string index out of range")
    p = self.maddr('%byte', a[0], f"{self.scalar('add', [Val(a[1], 'int'), Val(str(STR_HEADER_SIZE), 'int')])}")
    if name == "byte":
        return Val(self.scalar_cast('zext', Val(self.mload('%byte', p, data), '%byte'), 'int'), "int")
    self.guard(self.int_ucmp('>', Val(a[2], "int"), Val('255', "int")).v, "ValueError: byte must be in range(0, 256)")
    self.mstore('%byte', f"{self.scalar_cast('trunc', Val(a[2], 'int'), '%byte')}", p, data)
    return Val("null", "None")

def gen_iop(self, op: str, a: str, b: str) -> str:
    # checked 64-bit arithmetic (op: + - *): overflow raises OverflowError (CPython would grow the int)
    r = self.checked(op, a, b)
    self.guard(r[1], "OverflowError: integer result does not fit in 64 bits")
    return r[0]

def gen_notnone(self, v: Val, msg: str) -> None:
    # objects may be None (null); using one that is raises like CPython
    if v.t in self.classes and v.v not in self.nn:
        self.guard(self.ptr_cmp('==', v, Val('null', 'None')).v, msg)

def gen_unwrap(self, v: Val, msg: str) -> Val:
    # an optional value used where only the type it holds works: None raises msg ("Kind: text")
    if not is_opt(v.t):
        return v
    self.guard(self.ptr_cmp('==', v, Val('null', 'None')).v, msg)
    return self.deref(v)

def gen_deref(self, v: Val) -> Val:
    # an optional value known not to be None, as the value it holds: the same pointer, or an
    # int's, float's or bool's box read (a promoting int's two words: bigints.py)
    if not is_sopt(v.t):
        return Val(v.v, unopt(v.t)).identity(v)
    if v.t == BIGOPT:
        return self.big_unbox(v)
    return self.from_word(self.mload('int', v.v), unopt(v.t)).identity(v)

def gen_reboxes(self, a: str, b: str) -> bool:
    # is tuple type a tuple type b, but for items that are ints, floats or bools where b's may
    # be None (boxed), items that one of them holds as Any values (boxed, or unboxed with
    # dyn_unbox's check: dynamic.py), and that are as they are otherwise
    if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)) or a == b:
        return False
    for i in range(len(targs(a))):
        x = targs(a)[i]
        y = targs(b)[i]
        if x == "int+" and y != "int+":
            x = "int"  # (coerce narrows a promoting int item first, as 64-bit storage takes it: bigints.py)
        dyn = x != y and ((y == "dyn" and self.dyn_boxable(x) == "") or (x == "dyn" and self.dyn_boxable(y) == ""))
        big = y == "int+" and x == "int"  # (a promoting int holds it, bigints.py; the other way, coerce tests)
        fs = x == EMPTYFS and is_fset(unopt(y))  # (frozenset() that nothing typed: an empty one of y's, coerce)
        fs = fs or (x == "frozenset[dyn]" and x != y and is_fset(unopt(y)) and self.fset_unboxes(selem(unopt(y))))  # (one of Any values: a checked copy, coerce)
        if not self.widens(x, y) and not (is_sopt(y) and x == unopt(y)) and not self.uboxes(x, y) and not self.reboxes(x, y) and not self.vtuple_fits(x, y) and not dyn and not big and not fs:
            return False
    return True

def gen_convert_at(self, v: Val, t: str, label: str) -> Val:
    # v as a t, computed at the end of block label (before its terminator), where it reaches a
    # phi from: an int boxed as an int | None, an int | None known not to be None unboxed, or a
    # promoting int narrowed (bigints.py), whose test branches: convedge is then the block the
    # value reaches the phi from (label where no code does)
    self.convedge = label
    if not self.converts(v.t, t) and not narrows(v.t, t):
        return self.coerce(v, t)  # (no code)
    for b in self.fn.blocks:
        if b.label == label:
            return self.convert_in(v, t, b)
    if self.drying > 0:
        # (the block dry() began in is its own, in no list: its code is dropped, and only the
        # type is read)
        return Val(v.v, t)
    fail(f"internal error: no block {label} to convert {v.t} to {t} in", 0)
    return v

def gen_converts(self, a: str, b: str) -> bool:
    # does a value of type a take code to be one of type b (convert_in): also a runtime-length
    # tuple whose items each become a box (coerce's pys_vtuple_box), which a join of tuples makes
    return self.boxes(a, b) or (is_sopt(a) and b == unopt(a)) or (b == "int+" and a == "int") or (is_vtuple(a) and is_vtuple(unopt(b)) and is_sopt(targs(unopt(b))[0]) and targs(a)[0] == unopt(targs(unopt(b))[0]))

def gen_boxes(self, a: str, b: str) -> bool:
    # is a value of type a one of type b once boxed: an int as an int | None, a member as a
    # union, also as tuple items, and a value as a dynamic one (dynamic.py); and a fixed tuple
    # as a runtime-length one, a new tuple of its items (vtuple_fits)
    if b == "dyn":
        return a != "dyn" and self.dyn_boxable(a) == ""
    return (is_sopt(b) and a == unopt(b)) or (b == BIGOPT and a == "int") or self.uboxes(a, b) or self.reboxes(a, b) or self.vtuple_fits(a, b)

def gen_vtuple_fits(self, a: str, b: str) -> bool:
    # is fixed tuple type a one of runtime-length tuple type b (or b | None) once its items are
    # copied into a new tuple (coerce's vtuple_make): items of b's item type, or that are one
    # as they are or boxed; the empty tuple's too
    if not is_tuple(a) or not is_vtuple(unopt(b)):
        return False
    et = targs(unopt(b))[0]
    return all(x == et or self.widens(x, et) or self.boxes(x, et) for x in targs(a))

def gen_convert_in(self, v: Val, t: str, blk: Blk) -> Val:
    # v as a t, at the end of block blk, which has ended (see convert_at): a test the conversion
    # makes branches, and its end, convedge, is a block of its own, which takes blk's terminator
    here = self.blk
    cur = self.cur
    term = self.term
    handler = self.handler
    self.blk = blk
    last = blk.code.pop()
    self.cur = blk.label
    self.term = False
    self.handler = blk.handler  # (a test's raise goes where one in blk would)
    r = self.deref(v) if is_sopt(v.t) and t == unopt(v.t) else self.coerce(v, t)
    self.blk.code.append(last)
    self.convedge = self.cur
    self.blk = here
    self.cur = cur
    self.term = term
    self.handler = handler
    return r

def gen_sconst(self, s: str) -> str:
    if s in self.strs:
        return self.strs[s]
    name = f"@s.{len(self.strs)}"
    self.strs[s] = name
    self.strvals.append(s)
    d = Data("string", name)
    d.text = s
    self.consts.append(d)
    return name

def gen_bconst(self, s: str) -> str:
    # a bytes constant of s (a character per byte): a Str as a str constant is (sconst), but
    # named apart, so that no str folding takes its text and a str of the same bytes is another
    # object
    if s in self.bstrs:
        return self.bstrs[s]
    name = f"@b.{len(self.bstrs)}"
    self.bstrs[s] = name
    d = Data("string", name)
    d.text = s
    self.consts.append(d)
    return name

def gen_alloca(self, t: str, name: str) -> str:
    if t == "None":
        self.err(f"cannot infer the type of '{name}' from None; annotate it ({name}: T | None = None)")
    if t == "":
        self.err(f"cannot infer the type of '{name}'; add a type annotation")
    if name != "" and name in self.cells and name not in self.compvars:
        # a variable a closure takes: its cell, which the function allocated as it began (an int
        # of a module whose ints promote is a promoting int there, which a nonlocal write may
        # need: bigints.py)
        if t == "int" and self.int_policy(self.line):
            t = "int+"
        self.ltype[name] = t
        self.lreg[name] = self.cells[name]
        self.anyopt = self.anyopt or is_opt(t) or is_union(t) or t == "dyn" or t in self.classes
        if name in self.uflags:
            self.n += 1
            self.lflag[name] = f"%{name}.def.{self.n}"
            i = Ins("slot", "bool", name)
            i.k = 1
            i.r = one_num(self.n)
            self.slot(i)
        return self.cells[name]
    self.n += 1
    r = f"%{name or 'h'}.{self.n}"
    self.anyopt = self.anyopt or is_opt(t) or is_union(t) or t == "dyn" or t in self.classes
    i = Ins("slot", t, name)
    i.r = one_num(self.n)
    self.slot(i)
    if name != "":
        self.ltype[name] = t
        self.lreg[name] = r
        if name in self.uflags and name not in self.compvars:
            # "is assigned" flag for a local that some read may find unassigned
            self.lflag[name] = f"%{name}.def.{self.n}"
            i = Ins("slot", "bool", name)
            i.k = 1
            i.r = one_num(self.n)
            self.slot(i)
        if t == "str" and name in self.appends and name not in self.owned and name not in self.compvars:
            # the owned flag of a str local that the function appends to (str_append): one for
            # the name, which its later slots share, as every read and store of it clears the flag
            i = Ins("slot", "int", name + ".own")
            i.r = one_num(self.n)
            self.slot(i)
            self.owned[name] = f"%{name}.own.{self.n}"
        self.idbox.pop(name, "")
        if numeric_identity(t) and self.idhere() and (not self.fn.build.numeric_only or name in self.curfn.idnames):
            # the box of its binding as an Any value (idbox): null, as each slot is where the
            # function begins, until a store or its first crossing gives it one (dyn_box)
            i = Ins("slot", "dyn", name + ".box")
            i.r = one_num(self.n)
            self.slot(i)
            self.idbox[name] = f"%{name}.box.{self.n}"
            # Local generations distinguish an emitted store from one that actually runs.
            # This stack-only counter is dead when the value never needs identity.
            i = Ins("slot", "int", name + ".boxgen")
            i.r = one_num(self.n)
            self.slot(i)
    return r

# ---- value conversions
