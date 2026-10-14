"""Emission component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.ir import Blk, Frame, Ins, Val
from src.pystachy_compiler.specs import CHECKED, RTL, RTSYM, STRLEN_RANGE, TBAA_BYTES, TBAA_LEN
from src.pystachy_compiler.utils import (
    RtFn,
    is_opt,
    is_sopt,
    is_tuple,
    llstr,
    optnames,
    targs,
    typestr,
    unopt,
)


def gen_err(self, msg: str) -> None:
    if len(self.making) > 0:
        # an error in a template's function: say which call made it compile
        for i in range(len(self.making) - 1, -1, -1):
            msg += ("; " if i < len(self.making) - 1 else " (") + self.making[i]
        msg += ")"
    fail(optnames(msg) if "opt[" in msg else msg, self.line)

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
    fr.ret = self.ret
    fr.retann = self.retann
    fr.nn = self.nn
    fr.selfname = self.selfname
    fr.uflags = self.uflags
    fr.lflag = self.lflag
    fr.iflag = self.iflag
    fr.cells = self.cells
    fr.nlw = self.nlw
    fr.nonevars = self.nonevars
    fr.narrowed = self.narrowed
    fr.lkk = self.lkk
    fr.branch = self.branch
    fr.modlevel = self.modlevel
    fr.lenient = self.lenient
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
    self.ret = fr.ret
    self.retann = fr.retann
    self.nn = fr.nn
    self.selfname = fr.selfname
    self.uflags = fr.uflags
    self.lflag = fr.lflag
    self.iflag = fr.iflag
    self.cells = fr.cells
    self.nlw = fr.nlw
    self.nonevars = fr.nonevars
    self.narrowed = fr.narrowed
    self.lkk = fr.lkk
    self.branch = fr.branch
    self.modlevel = fr.modlevel
    self.lenient = fr.lenient
    self.n = fr.n
    self.cur = fr.cur
    self.term = fr.term
    self.line = fr.line

def gen_tmp(self) -> str:
    self.n += 1
    return f"%t{self.n}"

def gen_label(self) -> str:
    self.n += 1
    return f"L{self.n}"

def gen_emit(self, s: str) -> None:
    self.add(Ins("raw", "", s))

def gen_add(self, i: Ins) -> None:
    # code after a terminator (dead code) goes to a block of its own
    if self.term:
        self.place(self.label())
    self.blk.code.append(i)

def gen_put(self, i: Ins, k: int) -> None:
    # add i, which defines k values, numbered as k separate instructions would have been
    self.n += 1
    i.r = [self.n]
    self.add(i)
    for _ in range(k - 1):
        self.n += 1
        i.r.append(self.n)

def gen_ins(self, s: str) -> str:
    r = self.tmp()
    i = Ins("raw", "", f"{r} = {s}")
    i.k = self.n
    self.add(i)
    return r

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
    i.b = [l]
    self.blk.code.append(i)

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

def gen_ret_(self, v: Val) -> None:
    # return v (of type None: return nothing)
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
    return f"%t{ph.r[0]}"

def gen_select(self, c: str, x: Val, y: Val) -> str:
    # c ? x : y, where x and y have the same type
    i = Ins("select", x.t, "")
    i.a = [Val(c, "bool"), x, y]
    self.put(i, 1)
    return f"%t{i.r[0]}"

def gen_rt(self, name: str, ret: str, args: list[str]) -> str:
    # an rt op: a call of runtime function name (its LLVM symbol), whose LLVM result type is
    # ret, with args "<LLVM type> <value>", which must be what its RUNTIME entry says. (In
    # runtime mode, a function that runtime.py defines is called the same way: it is defined,
    # not declared, with RUNTIME's types, which Gen.function checks.)
    if self.rtmode and "@" + name == self.curfn.ll:
        self.err(f"{name}() implements an operation that it uses: write it without that operation")
    k = self.runtime(name)
    ts = self.rtfns[k].sig
    ll = self.rtfns[k].ll
    ok = ret == ll[0] and len(args) == len(ll) - 1
    i = Ins("rt", ts[0], k)
    i.a = []
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
        fail(f"internal error: {name} called as {ret} ({', '.join(args)}), but RUNTIME declares it as {self.rtfns[k].decl}", 0)
    if ret == "void":
        self.add(i)
        return ""
    self.put(i, 1)
    return f"%t{i.r[0]}"

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
    return [f"%t{i.r[1]}", f"%t{i.r[2]}"]

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
    if name == "wrap_add" or name == "wrap_sub" or name == "wrap_mul":
        return Val(self.ins(f"{name[5:]} i64 {a[0]}, {a[1]}"), "int")
    if name == "udiv" or name == "urem":
        self.guard(self.ins(f"icmp eq i64 {a[1]}, 0"), "ZeroDivisionError: integer division or modulo by zero")
        return Val(self.ins(f"{name} i64 {a[0]}, {a[1]}"), "int")
    if name == "mul_ovf":
        return Val(self.checked("*", a[0], a[1])[1], "bool")
    if name == "shl" or name == "lshr":
        # by n mod 64, as the hardware shifts (LLVM would make a larger shift poison)
        return Val(self.ins(f"{name} i64 {a[0]}, {self.ins(f'and i64 {a[1]}, 63')}"), "int")
    if name == "str_done":
        return vals[0]
    if name == "null":
        return Val(self.ins(f"icmp eq ptr {a[0]}, null"), "bool")
    if name == "same":
        # same(a, i, b, j, n): within both, and n >= 0
        n0 = self.ins(f"load i64, ptr {a[0]}, !tbaa !{TBAA_LEN}, !range !{STRLEN_RANGE}")
        n1 = self.ins(f"load i64, ptr {a[2]}, !tbaa !{TBAA_LEN}, !range !{STRLEN_RANGE}")
        for x in [f"icmp slt i64 {a[4]}, 0", f"icmp ugt i64 {a[1]}, {n0}", f"icmp ugt i64 {a[4]}, {self.ins(f'sub i64 {n0}, {a[1]}')}",
                  f"icmp ugt i64 {a[3]}, {n1}", f"icmp ugt i64 {a[4]}, {self.ins(f'sub i64 {n1}, {a[3]}')}"]:
            self.guard(self.ins(x), "IndexError: compare out of range")
        p0 = self.ins(f"getelementptr i8, ptr {a[0]}, i64 {self.ins(f'add i64 {a[1]}, 16')}")
        p1 = self.ins(f"getelementptr i8, ptr {a[2]}, i64 {self.ins(f'add i64 {a[3]}, 16')}")
        return Val(self.ins(f"icmp eq i32 {self.rt('memcmp', 'i32', [f'ptr {p0}', f'ptr {p1}', f'i64 {a[4]}'])}, 0"), "bool")
    if name == "find_byte":
        # find_byte(s, c, st, en): 0 <= st <= en <= len(s)
        n0 = self.ins(f"load i64, ptr {a[0]}, !tbaa !{TBAA_LEN}, !range !{STRLEN_RANGE}")
        for x in [f"icmp ugt i64 {a[3]}, {n0}", f"icmp ugt i64 {a[2]}, {a[3]}"]:
            self.guard(self.ins(x), "IndexError: search out of range")
        self.guard(self.ins(f"icmp ugt i64 {a[1]}, 255"), "ValueError: byte must be in range(0, 256)")
        p0 = self.ins(f"getelementptr i8, ptr {a[0]}, i64 {self.ins(f'add i64 {a[2]}, 16')}")
        f = self.rt("memchr", "ptr", [f"ptr {p0}", f"i32 {self.ins(f'trunc i64 {a[1]} to i32')}", f"i64 {self.ins(f'sub i64 {a[3]}, {a[2]}')}"])
        d = self.ins(f"sub i64 {self.ins(f'ptrtoint ptr {f} to i64')}, {self.ins(f'ptrtoint ptr {a[0]} to i64')}")
        return Val(self.ins(f"select i1 {self.ins(f'icmp eq ptr {f}, null')}, i64 -1, i64 {self.ins(f'sub i64 {d}, 16')}"), "int")
    if name == "find_sub":
        # find_sub(h, n, st, en): 0 <= st <= en <= len(h)
        n0 = self.ins(f"load i64, ptr {a[0]}, !tbaa !{TBAA_LEN}, !range !{STRLEN_RANGE}")
        for x in [f"icmp ugt i64 {a[3]}, {n0}", f"icmp ugt i64 {a[2]}, {a[3]}"]:
            self.guard(self.ins(x), "IndexError: search out of range")
        p0 = self.ins(f"getelementptr i8, ptr {a[0]}, i64 {self.ins(f'add i64 {a[2]}, 16')}")
        p1 = self.ins(f"getelementptr i8, ptr {a[1]}, i64 16")
        m = self.ins(f"load i64, ptr {a[1]}, !tbaa !{TBAA_LEN}, !range !{STRLEN_RANGE}")
        f = self.rt("memmem", "ptr", [f"ptr {p0}", f"i64 {self.ins(f'sub i64 {a[3]}, {a[2]}')}", f"ptr {p1}", f"i64 {m}"])
        d = self.ins(f"sub i64 {self.ins(f'ptrtoint ptr {f} to i64')}, {self.ins(f'ptrtoint ptr {a[0]} to i64')}")
        return Val(self.ins(f"select i1 {self.ins(f'icmp eq ptr {f}, null')}, i64 -1, i64 {self.ins(f'sub i64 {d}, 16')}"), "int")
    if name == "str_new":
        # a size the allocator cannot serve (negative, or past 2**63 with the header and NUL)
        # is CPython's MemoryError, as in runtime.c
        self.guard(self.ins(f"icmp ugt i64 {a[0]}, 9223372036854775790"), "MemoryError: ")
        r = self.rt("pys_alloc_atomic", "ptr", [f"i64 {self.ins(f'add nuw nsw i64 {a[0]}, 17')}"])  # zeroed: dict_hash and NUL
        self.emit(f"store i64 {a[0]}, ptr {r}, !tbaa !{TBAA_LEN}")
        return Val(r, "str")
    # the others index a str: an unsigned compare with its length also rejects a negative index
    n = self.ins(f"load i64, ptr {a[0]}, !tbaa !{TBAA_LEN}, !range !{STRLEN_RANGE}")
    if name == "copy":
        # copy(dst, at, src, lo, n): dst[at:at + n] = src[lo:lo + n], within both
        m = self.ins(f"load i64, ptr {a[2]}, !tbaa !{TBAA_LEN}, !range !{STRLEN_RANGE}")
        for x in [f"icmp slt i64 {a[4]}, 0", f"icmp ugt i64 {a[1]}, {n}", f"icmp ugt i64 {a[4]}, {self.ins(f'sub i64 {n}, {a[1]}')}",
                  f"icmp ugt i64 {a[3]}, {m}", f"icmp ugt i64 {a[4]}, {self.ins(f'sub i64 {m}, {a[3]}')}"]:
            self.guard(self.ins(x), "IndexError: copy out of range")
        dst = self.ins(f"getelementptr i8, ptr {a[0]}, i64 {self.ins(f'add i64 {a[1]}, 16')}")
        src = self.ins(f"getelementptr i8, ptr {a[2]}, i64 {self.ins(f'add i64 {a[3]}, 16')}")
        self.rt("llvm.memmove.p0.p0.i64", "void", [f"ptr {dst}", f"ptr {src}", f"i64 {a[4]}", "i1 false"])
        return Val("null", "None")
    self.guard(self.ins(f"icmp uge i64 {a[1]}, {n}"), "IndexError: string index out of range")
    p = self.ins(f"getelementptr i8, ptr {a[0]}, i64 {self.ins(f'add i64 {a[1]}, 16')}")
    if name == "byte":
        return Val(self.ins(f"zext i8 {self.ins(f'load i8, ptr {p}, !tbaa !{TBAA_BYTES}')} to i64"), "int")
    self.guard(self.ins(f"icmp ugt i64 {a[2]}, 255"), "ValueError: byte must be in range(0, 256)")
    self.emit(f"store i8 {self.ins(f'trunc i64 {a[2]} to i8')}, ptr {p}, !tbaa !{TBAA_BYTES}")
    return Val("null", "None")

def gen_iop(self, op: str, a: str, b: str) -> str:
    # checked 64-bit arithmetic (op: + - *): overflow raises OverflowError (CPython would grow the int)
    r = self.checked(op, a, b)
    self.guard(r[1], "OverflowError: integer result does not fit in 64 bits")
    return r[0]

def gen_notnone(self, v: Val, msg: str) -> None:
    # objects may be None (null); using one that is raises like CPython
    if v.t in self.classes and v.v not in self.nn:
        self.guard(self.ins(f"icmp eq ptr {v.v}, null"), msg)

def gen_unwrap(self, v: Val, msg: str) -> Val:
    # an optional value used where only the type it holds works: None raises msg ("Kind: text")
    if not is_opt(v.t):
        return v
    self.guard(self.ins(f"icmp eq ptr {v.v}, null"), msg)
    return self.deref(v)

def gen_deref(self, v: Val) -> Val:
    # an optional value known not to be None, as the value it holds: the same pointer, or an
    # int's, float's or bool's box read
    if not is_sopt(v.t):
        return Val(v.v, unopt(v.t))
    return self.from_slot(self.ins(f"load i64, ptr {v.v}"), unopt(v.t))

def gen_reboxes(self, a: str, b: str) -> bool:
    # is tuple type a tuple type b, but for items that are ints, floats or bools where b's may
    # be None (boxed), and that are as they are otherwise
    if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)) or a == b:
        return False
    for i in range(len(targs(a))):
        x = targs(a)[i]
        y = targs(b)[i]
        if not self.widens(x, y) and not (is_sopt(y) and x == unopt(y)) and not self.reboxes(x, y):
            return False
    return True

def gen_convert_at(self, v: Val, t: str, label: str) -> Val:
    # v as a t, computed at the end of block label (before its terminator), where it reaches a
    # phi from: an int boxed as an int | None, or an int | None known not to be None unboxed
    if not self.converts(v.t, t):
        return self.coerce(v, t)  # (no code)
    for b in self.fn.blocks:
        if b.label == label:
            return self.convert_in(v, t, b)
    fail(f"internal error: no block {label} to convert {v.t} to {t} in", 0)
    return v

def gen_converts(self, a: str, b: str) -> bool:
    # does a value of type a take code to be one of type b (convert_in)
    return self.boxes(a, b) or (is_sopt(a) and b == unopt(a))

def gen_boxes(self, a: str, b: str) -> bool:
    # is a value of type a one of type b once boxed: an int as an int | None, also as tuple items
    return (is_sopt(b) and a == unopt(b)) or self.reboxes(a, b)

def gen_convert_in(self, v: Val, t: str, blk: Blk) -> Val:
    # v as a t, at the end of block blk, which has ended (see convert_at)
    here = self.blk
    cur = self.cur
    term = self.term
    self.blk = blk
    last = blk.code.pop()
    self.cur = blk.label
    self.term = False
    r = self.deref(v) if is_sopt(v.t) and t == unopt(v.t) else self.coerce(v, t)
    blk.code.append(last)
    self.blk = here
    self.cur = cur
    self.term = term
    return r

def gen_sconst(self, s: str) -> str:
    if s in self.strs:
        return self.strs[s]
    name = f"@s.{len(self.strs)}"
    self.strs[s] = name
    self.strvals.append(s)
    n = len(s) + 1
    # Bytes stay immutable; the dictionary hash cache must be writable (runtime.c Str).
    self.consts.append(f'{name} = private unnamed_addr global {{i64, i64, [{n} x i8]}} {{i64 {n - 1}, i64 0, [{n} x i8] c"{llstr(s)}\\00"}}, align 8')
    return name

def gen_alloca(self, t: str, name: str) -> str:
    if t == "None":
        self.err(f"cannot infer the type of '{name}' from None; annotate it ({name}: T | None = None)")
    if t == "":
        self.err(f"cannot infer the type of '{name}'; add a type annotation")
    if name != "" and name in self.cells and name not in self.compvars:
        # a variable a closure takes: its cell, which the function allocated as it began
        self.ltype[name] = t
        self.lreg[name] = self.cells[name]
        self.anyopt = self.anyopt or is_opt(t)
        if name in self.uflags:
            self.n += 1
            self.lflag[name] = f"%{name}.def.{self.n}"
            i = Ins("slot", "bool", name)
            i.k = 1
            i.r = [self.n]
            self.fn.slots.append(i)
        return self.cells[name]
    self.n += 1
    r = f"%{name or 'h'}.{self.n}"
    self.anyopt = self.anyopt or is_opt(t)
    i = Ins("slot", t, name)
    i.r = [self.n]
    self.fn.slots.append(i)
    if name != "":
        self.ltype[name] = t
        self.lreg[name] = r
        if name in self.uflags and name not in self.compvars:
            # "is assigned" flag for a local that some read may find unassigned
            self.lflag[name] = f"%{name}.def.{self.n}"
            i = Ins("slot", "bool", name)
            i.k = 1
            i.r = [self.n]
            self.fn.slots.append(i)
    return r

# ---- value conversions
