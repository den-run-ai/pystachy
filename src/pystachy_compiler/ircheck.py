"""Ircheck component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.ir import Blk, IFn, Ins
from src.pystachy_compiler.specs import FXALL, FXBIT, IROPS, LLNOTRAW, RUNTIME
from src.pystachy_compiler.utils import rawfx


def gen_verify(self, fn: IFn, eh: bool) -> None:
    # PYSTACHY_IRCHECK=1: fn is well formed. Every op is in IROPS, an rt op's key in RUNTIME;
    # a raw op is one LLVM instruction that is no call (calls are rt, call and init ops, whose
    # effects are known), no phi and no terminator, and call and init ops call compiled
    # functions (or, in runtime mode, runtime.c's functions that runtime.py declares); every block ends with its one terminator; branches go to blocks of fn; a phi
    # starts its block, and its predecessors branch there; each op holds exactly the numbers
    # its lowering prints (Ins.r), and no number or label is above IFn.n. Exceptions (once the
    # passes of eh_ir have run, eh): a landing op is alone in its block, which only the unwind
    # edges of invokes reach, and every invoke's unwind edge goes to one; in a block that a
    # try statement covers, no call that may raise is left a call, nor a raise or throw
    at: dict[str, int] = {}
    lands: dict[str, bool] = {}
    for b in fn.blocks:
        if len(b.code) > 0 and b.code[0].op == "landing":
            lands[b.label] = True
    for i in fn.slots:
        if i.op != "slot" or len(i.r) != 1:
            self.bad_ir(fn, fn.blocks[0], f"a {i.op} op among the slots, with {len(i.r)} numbers")
        if i.r[0] > fn.n:
            self.bad_ir(fn, fn.blocks[0], f"the slot of {i.s} numbered {i.r[0]}, above IFn.n ({fn.n})")
    for j in range(len(fn.blocks)):
        l = fn.blocks[j].label
        if l in at:
            self.bad_ir(fn, fn.blocks[j], "a second block of that name")
        if l.startswith("L") and int(l[1:]) > fn.n:
            self.bad_ir(fn, fn.blocks[j], f"a label above IFn.n ({fn.n})")
        at[l] = j
    succ: list[list[str]] = []
    for b in fn.blocks:
        out: list[str] = []
        for j in range(len(b.code)):
            i = b.code[j]
            if i.op not in IROPS:
                self.bad_ir(fn, b, f"unknown op {i.op}")
            inv = len(i.b) == 2 and (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init")
            if ("T" in IROPS[i.op] or inv) != (j == len(b.code) - 1):
                self.bad_ir(fn, b, f"a terminator in the middle, at {i.op}" if j < len(b.code) - 1 else f"no terminator, last {i.op}")
            if i.op == "landing" and j > 0:
                self.bad_ir(fn, b, "a landing op after other ops")
            if inv and i.b[1] not in lands:
                self.bad_ir(fn, b, f"an invoke whose unwind edge goes to {i.b[1]}, which is no landing block")
            for l in i.b[:1] if inv else i.b if i.op != "phi" else i.b[:0]:
                if l in lands:
                    self.bad_ir(fn, b, f"a branch to the landing block {l}, which only unwind edges may reach")
            if eh and b.handler != "" and (i.op == "raise" or i.op == "throw" or (not inv and (i.op == "rt" or i.op == "call" or i.op == "icall" or i.op == "init") and self.opfx(i, fn.fa) & FXBIT["R"] != 0)):
                self.bad_ir(fn, b, f"{i.op} {i.s} may raise, in a block {b.handler} covers, but goes to no landing block")
            if i.op == "phi" and j > 0 and b.code[j - 1].op != "phi":
                self.bad_ir(fn, b, "a phi after other ops")
            if i.op == "rt" and i.s not in self.rtfns:
                self.bad_ir(fn, b, f"no RUNTIME entry for {i.s}" if i.s not in RUNTIME else f"{i.s}, which runtime() did not declare")
            n = self.nums(i)
            if len(i.r) != n:
                self.bad_ir(fn, b, f"{i.op} {i.s} with {len(i.r)} numbers, where its lowering prints {n}")
            for x in i.r:
                if x > fn.n:
                    self.bad_ir(fn, b, f"{i.op} {i.s} numbered {x}, above IFn.n ({fn.n})")
            if i.op == "raw":
                # one LLVM instruction that loads, stores or computes: not a call, a phi, a
                # terminator or a label (its first word, after the "%x = " of a value it defines)
                w = i.s[i.s.find(" = ") + 3 :] if i.s.startswith("%") and " = " in i.s else i.s
                w = w[: w.find(" ")] if " " in w else w
                if w in LLNOTRAW or w.endswith(":") or "\n" in i.s:
                    self.bad_ir(fn, b, f"LLVM text that must be an op: {i.s}")
            if (i.op == "call" and i.s not in self.fll and i.s not in self.externs) or (i.op == "init" and "@init." + i.s not in self.fll):
                self.bad_ir(fn, b, f"a call of {i.s}, which is not compiled")
            if i.op != "phi":
                out.extend(i.b)
            if i.op == "check":
                ck = i.x if i.x != "" else i.s
                out.append(fn.cold[ck] if ck in fn.cold else f"(none for {ck})")
        if len(b.code) == 0:
            self.bad_ir(fn, b, "no terminator")
        for l in out:
            if l not in at or l == "entry":
                self.bad_ir(fn, b, f"a branch to {l}, which is no block of it")
        succ.append(out)
    for b in fn.blocks:
        for i in b.code:
            if i.op == "phi":
                for l in i.b:
                    if l not in at or b.label not in succ[at[l]]:
                        self.bad_ir(fn, b, f"a phi from {l}, which does not branch there")

def gen_nums(self, i: Ins) -> int:
    # how many numbers op i defines (%tN): what its lowering prints
    if i.op == "ovf":
        return 3
    if i.op == "list.load":
        return 4
    if i.op == "landing" or i.op == "exc.match":
        return 2
    if i.op == "phi" or i.op == "select" or i.op == "list.len":
        return 1
    if i.op == "rt":
        return 0 if self.rtfns[i.s].sig[0] == "None" else 1
    if i.op == "call" or i.op == "icall":
        return 0 if i.t == "None" else 1
    return 0

def gen_bad_ir(self, fn: IFn, b: Blk, what: str) -> None:
    fail(f"internal error: bad IR in {fn.f.ll}, block {b.label or '(unnamed)'}: {what}", 0)

def gen_effects(self) -> None:
    # each function's effect summary (IFn.fx): the letters of its ops, where a call or an init
    # counts with its callee's summary; a fixpoint over the call graph, from no letters
    calls: list[list[int]] = []
    for fn in self.fns:
        m = 0
        cs: list[int] = []
        for b in fn.blocks:
            for i in b.code:
                if i.op == "raw":
                    m |= rawfx(i.s, fn.fa)
                elif i.op == "call" and i.s in self.fll:
                    cs.append(self.fll[i.s])
                elif i.op == "init" and "@init." + i.s in self.fll:
                    cs.append(self.fll["@init." + i.s])
                else:
                    m |= self.opfx(i, fn.fa)
        fn.fx = m & ~FXBIT["N"]
        calls.append(cs)
    more = True
    while more:
        more = False
        for j in range(len(self.fns)):
            m = self.fns[j].fx
            for x in calls[j]:
                m |= self.fns[x].fx
            if m != self.fns[j].fx:
                self.fns[j].fx = m
                more = True

def gen_opfx(self, i: Ins, fa: dict[str, bool]) -> int:
    # the effects of op i (FX bits) of a function whose field addresses are fa (IFn.fa): a
    # call's and an init's are its callee's summary (IFn.fx: every letter until effects has
    # computed it, and if the callee is not compiled), a raw op's what its text does (rawfx)
    if i.op == "call" or i.op == "init":
        c = i.s if i.op == "call" else "@init." + i.s
        return self.fns[self.fll[c]].fx if c in self.fll else FXALL
    if i.op == "icall":
        return FXALL  # (a Callable's code: any function of its type)
    if i.op == "rt":
        # (an exception, E, may be an object of an exception class, whose __str__ and __repr__ run)
        f = self.rtfns[i.s]
        return FXALL if f.q and ("O" in i.x or ("E" in i.x and len(self.xcls) > 0)) else f.fx
    if i.op == "raw":
        return rawfx(i.s, fa)
    return self.opfxs[i.op]

# ---- optimizations (OPTS): passes over an IFn, once the program is built and its effect
# summaries computed, that rewrite ops into cheaper ones (docs/typed-ir.md 7.1)
