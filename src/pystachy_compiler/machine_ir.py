"""Machine lowering of typed IR: reads of a runtime layout become machine operations.

Through the passes and proofs, typed IR says what a read means: a list's length, a closed
union's tag, a dynamic box's payload. Those ops keep their receiver's type, their effects and
their guard proofs. Once exception lowering is done nothing reads that meaning any more, and
Gen.machine_ir rewrites each such op into the machine address and load ops (memory_ir.py)
that every other header read already is. The layouts are one table here, WORD_READS, so the
backend that prints a function (lowering.py) holds no copy of them and prints fewer kinds of
op. The rewrite changes no value number, label or line, and so no LLVM text.
"""
from __future__ import annotations
import os
from src.pystachy_compiler.ir import IFn, Ins, Val, one_num, tmpname

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
