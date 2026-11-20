"""Machine lowering of typed IR: reads of a runtime layout become machine operations.

Through the passes and proofs, typed IR says what a read means: a list's length, a closed
union's tag, a dynamic box's payload. Those ops keep their receiver's type, their effects and
their guard proofs. Once exception lowering is done nothing reads that meaning any more, and
Gen.machine_ir rewrites each such op into the machine address and load ops (memory_ir.py)
that every other header read already is. The layouts are one table here, WORD_READS, so the
backend that prints a function (lowering.py) holds no copy of them and prints fewer kinds of
op. The rewrite changes no value number, label or line, and so no LLVM text.

Before it, Gen.erase_casts takes the casts out (a cast reads its operand at another type of the
same LLVM type, and lowers to no instruction), with their numbers, so that the LLVM text is what
it would be had the frontend and the passes made no cast.
"""
from __future__ import annotations
import os
from src.pystachy_compiler.ir import OPERAND_SLOT, OPERAND_VALUE, IFn, Ins, Val, digits, one_num, operand_kind, tmpname

# A layout read and the 8-byte word of its operand's object that it reads, as runtime.c lays
# them out: a List is {len, cap, items}, a closed union's box {tag, payload} and a dynamic
# value's box {DynType, payload}. The op's own type is the word's: an int, a DynType or the
# opaque %slot of a payload, whose bits a slot.unpack or an identity test then reads
WORD_READS: dict[str, int] = {
    "list.len": 0, "union.tag": 0, "dyn.type": 0,
    "union.payload": 1, "union.raw": 1, "dyn.payload": 1, "dyn.raw": 1,
}


def machine_ops(i: Ins) -> list[Ins]:
    # the machine ops of layout read i (an op of WORD_READS): a load of the object's first word,
    # or the address of a later word (its first number) and a load from it (its second). They
    # keep i's numbers, in the order its lowering printed them, and its source line
    word = WORD_READS[i.op]
    p = i.a[0].v
    out: list[Ins] = []
    if word > 0:
        addr = Ins("mach.addr", "%ptr", "int")
        addr.line = i.line
        addr.a = [Val(p, "%ptr"), Val(str(word), "int")]
        addr.r = one_num(i.r[0])
        out.append(addr)
        p = tmpname(i.r[0])
    load = Ins("mach.load", i.t, "")
    load.line = i.line
    load.a = [Val(p, "%ptr")]
    load.r = one_num(i.r[len(i.r) - 1])
    out.append(load)
    return out


def gen_machine_ir(self, fn: IFn) -> None:
    # the last stage before fn is printed (Gen.lower runs it first): every layout read of fn
    # becomes its machine ops. A block without one keeps its list of ops; another gets a new
    # list, and its ops stay as they are (an Ins may be a clone's source: optimizations.py)
    for b in fn.blocks:
        code = b.code
        for j in range(len(code)):
            if code[j].op in WORD_READS:
                out = code[:j]
                for i in code[j:]:
                    if i.op in WORD_READS:
                        out.extend(machine_ops(i))
                    else:
                        out.append(i)
                b.code = out
                break
    if os.getenv("PYSTACHY_IRCHECK", "") == "1":
        self.verify_machine(fn)


def gen_verify_machine(self, fn: IFn) -> None:
    # PYSTACHY_IRCHECK=1, once machine_ir has run: no op that has a machine lowering is left
    # for the backend, and every machine memory op, the frontend's and this stage's, has the
    # shape Gen.verify asks of one. A machine load may now give a payload's opaque %slot
    for b in fn.blocks:
        for i in b.code:
            if i.op in WORD_READS:
                self.bad_ir(fn, b, f"{i.op} left after machine lowering")
            if i.op == "mach.load" or i.op == "mach.store" or i.op == "mach.addr":
                self.verify_memory(fn, b, i, True)
                if len(i.r) != self.nums(i):
                    self.bad_ir(fn, b, f"{i.op} with {len(i.r)} numbers, where its lowering prints {self.nums(i)}")


def renamed(s: str, first: int, renum: list[int]) -> str:
    # s, which names a value (%tN), a slot's register (%name.N) or a label (LN), with its number N
    # as erase_casts gives it: renum[N - first] where N is first or above, else N
    k = operand_kind(s)
    at = 2 if k == OPERAND_VALUE else s.rfind(".") + 1 if k == OPERAND_SLOT else 1 if len(s) > 1 and s[0] == "L" and digits(s, 1, len(s)) else -1
    if at < 0:
        return s
    n = int(s[at:])
    if n < first or n - first >= len(renum):
        return s
    return tmpname(renum[n - first]) if k == OPERAND_VALUE else s[:at] + str(renum[n - first])


def rekeyed(k: str, first: int, renum: list[int]) -> str:
    # a check's key (IFn.cold): its message, after its landing block's label in a try statement
    sp = k.find(" ")
    return renamed(k[:sp], first, renum) + k[sp:] if sp > 1 and k[0] == "L" and digits(k, 1, sp) else k


def gen_erase_casts(self, fn: IFn) -> None:
    # the first stage of fn's lowering (Gen.lower): a cast lowers to no instruction, so each goes,
    # and an operand that reads one reads what it casts, at its own type (a cast keeps its
    # operand's LLVM type). Its number goes too: every number above a cast's is one less for each
    # cast below it, the number it would have had had no cast been made. A function's casts are
    # numbered after its last value (Gen.number_casts), and a pass numbers what it adds after
    # them, a cast as any other value: its numbers, as the LLVM text, are then those of the
    # function and passes that made no cast
    source: dict[str, str] = {}
    numbered: dict[int, bool] = {}
    for n in fn.casts:
        numbered[n] = True  # (a pass may have dropped a cast that nothing read: its number goes too)
    for b in fn.blocks:
        kept: list[Ins] = []
        for i in b.code:
            if i.op == "cast":
                source[tmpname(i.r[0])] = i.a[0].v
                numbered[i.r[0]] = True
            else:
                kept.append(i)
        if len(kept) < len(b.code):
            b.code = kept
    if len(numbered) == 0:
        return
    for v in [x for x in source]:
        x = source[v]
        while x in source:
            x = source[x]  # (a cast of a cast's value reads what the first casts)
        source[v] = x
    gone = sorted([n for n in numbered])
    first = gone[0]
    renum: list[int] = []
    j = 0
    for m in range(first, fn.n + 1):
        while j < len(gone) and gone[j] < m:
            j += 1
        renum.append(m - j)
    fn.n -= len(gone)
    fn.casts = []
    for i in fn.slots:
        if i.r[0] >= first:
            i.r = one_num(renum[i.r[0] - first])
    prefix = fn.f.ll + " "
    moved: list[str] = []  # (the keys of its calls in Gen.vcalls, each before its new one)
    for b in fn.blocks:
        b.label = renamed(b.label, first, renum)
        b.handler = renamed(b.handler, first, renum)
        for i in b.code:
            if len([n for n in i.r if n >= first]) > 0:
                if i.op == "call" and len(i.r) == 1 and prefix + tmpname(i.r[0]) in self.vcalls:
                    moved.append(prefix + tmpname(i.r[0]))
                    moved.append(prefix + tmpname(renum[i.r[0] - first]))
                i.r = one_num(renum[i.r[0] - first]) if len(i.r) == 1 else [renum[n - first] if n >= first else n for n in i.r]
            if len([a for a in i.a if a.v in source or renamed(a.v, first, renum) != a.v]) > 0:
                i.a = [Val(renamed(source[a.v] if a.v in source else a.v, first, renum), a.t) for a in i.a]
            if len([l for l in i.b if renamed(l, first, renum) != l]) > 0:
                i.b = [renamed(l, first, renum) for l in i.b]
            if i.op == "check":
                i.x = rekeyed(i.x, first, renum)
    cold: dict[str, str] = {}
    for k in fn.cold:
        cold[rekeyed(k, first, renum)] = renamed(fn.cold[k], first, renum)
    fn.cold = cold
    coldh: dict[str, str] = {}
    for k in fn.coldh:
        coldh[rekeyed(k, first, renum)] = renamed(fn.coldh[k], first, renum)
    fn.coldh = coldh
    fa: dict[str, bool] = {}
    for v in fn.fa:
        fa[renamed(v, first, renum)] = True
    fn.fa = fa
    fn.rdepth = renamed(fn.rdepth, first, renum)
    fn.gdepth = renamed(fn.gdepth, first, renum)
    fn.gpad = renamed(fn.gpad, first, renum)
    fn.gbase = renamed(fn.gbase, first, renum)
    fn.gsaved = renamed(fn.gsaved, first, renum)
    fn.gouter = renamed(fn.gouter, first, renum)
    fn.ghand = renamed(fn.ghand, first, renum)
    # (all old keys go before any new one is added, which may be another call's old key)
    for j in range(0, len(moved), 2):
        del self.vcalls[moved[j]]
    for j in range(1, len(moved), 2):
        self.vcalls[moved[j]] = True
