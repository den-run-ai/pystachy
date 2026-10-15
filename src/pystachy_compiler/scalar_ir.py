"""Typed machine scalar computations; LLVM spellings are chosen only at lowering."""
from __future__ import annotations
from src.pystachy_compiler.ir import Blk, IFn, Ins, Val


SCALAR_INTS = ["bool", "%byte", "%i32", "int"]
SCALAR_BIN = ["add", "sub", "mul", "udiv", "urem", "shl", "lshr", "ashr", "and", "or", "xor"]
SCALAR_FLOAT = ["fadd", "fsub", "fmul", "fdiv", "fneg"]
SCALAR_ICMP = ["eq", "ne", "slt", "sle", "sgt", "sge", "ult", "ule", "ugt", "uge"]
SCALAR_FCMP = ["oeq", "one", "olt", "ole", "ogt", "oge", "ueq", "une", "ult", "ule", "ugt", "uge", "ord", "uno"]
SCALAR_CASTS = ["zext:bool:int", "zext:%byte:int", "trunc:int:bool", "trunc:int:%byte", "trunc:int:%i32", "sitofp:int:float", "fptosi:float:int", "ptrtoint:%ptr:int"]


def gen_scalar(self, op: str, args: list[Val], flags: str = "") -> str:
    i = Ins("scalar.bin", args[0].t, op)
    i.a = args
    i.x = flags
    self.put(i, 1)
    return f"%t{i.r[0]}"


def gen_scalar_cast(self, op: str, a: Val, t: str) -> str:
    i = Ins("scalar.cast", t, op)
    i.a = [a]
    self.put(i, 1)
    return f"%t{i.r[0]}"


def gen_scalar_cmp(self, predicate: str, a: Val, b: Val) -> str:
    i = Ins("scalar.cmp", "bool", predicate)
    i.a = [a, b]
    self.put(i, 1)
    return f"%t{i.r[0]}"




def gen_verify_scalar(self, fn: IFn, b: Blk, i: Ins) -> None:
    if i.k != 0 or len(i.b) != 0 or len(i.r) != 1:
        self.bad_ir(fn, b, f"{i.op} needs one result and no integer immediate or labels")
    if i.op == "scalar.bin":
        if len(i.a) != (1 if i.s == "fneg" else 2):
            self.bad_ir(fn, b, "scalar.bin has invalid operand count")
        t = i.a[0].t
        if i.t != t or (len(i.a) == 2 and i.a[1].t != t):
            self.bad_ir(fn, b, "scalar.bin needs matching operand and result types")
        if not ((t in SCALAR_INTS and i.s in SCALAR_BIN) or (t == "float" and i.s in SCALAR_FLOAT)):
            self.bad_ir(fn, b, "scalar.bin has invalid operator for its type")
        if i.x != "" and (i.s not in ["add", "sub", "mul"] or i.x not in ["nsw", "nuw", "nuw nsw"]):
            self.bad_ir(fn, b, "scalar.bin has invalid overflow flags")
    elif i.op == "scalar.cast":
        if len(i.a) != 1 or i.x != "":
            self.bad_ir(fn, b, "scalar.cast needs one operand and no flags")
        if i.s + ":" + i.a[0].t + ":" + i.t not in SCALAR_CASTS:
            self.bad_ir(fn, b, "scalar.cast has invalid conversion")
    else:
        if len(i.a) != 2 or i.t != "bool" or i.x != "":
            self.bad_ir(fn, b, "scalar.cmp needs two operands, bool result and no flags")
        t = i.a[0].t
        if i.a[1].t != t or not ((t in SCALAR_INTS and i.s in SCALAR_ICMP) or (t == "float" and i.s in SCALAR_FCMP) or (t == "%ptr" and i.s in ["eq", "ne"])):
            self.bad_ir(fn, b, "scalar.cmp has invalid comparison for its type")
