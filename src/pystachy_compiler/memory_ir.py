"""Typed operations for compiler-owned machine storage and indexed addresses.

Native mem.load/store retain the stronger *<native> address contract. These
operations also cover closure environments, runtime headers and byte buffers.
"""
from __future__ import annotations
from src.pystachy_compiler.ir import Blk, IFn, Ins, Val, tmpname


def gen_mload(self, t: str, p: str, metadata: str = "") -> str:
    i = Ins("mach.load", t, metadata)
    i.a = [Val(p, "%ptr")]
    self.put(i, 1)
    return tmpname(i.r[0])


def gen_mstore(self, t: str, v: str, p: str, metadata: str = "") -> None:
    i = Ins("mach.store", "", metadata)
    i.a = [Val(p, "%ptr"), Val(v, t)]
    self.add(i)


def gen_maddr(self, t: str, p: str, index: str, inbounds: bool = False) -> str:
    i = Ins("mach.addr", "%ptr", t)
    i.a = [Val(p, "%ptr"), Val(index, "int")]
    i.k = 1 if inbounds else 0
    self.put(i, 1)
    return tmpname(i.r[0])


def gen_verify_memory(self, fn: IFn, b: Blk, i: Ins, slots: bool) -> None:
    # the shape of machine memory op i (PYSTACHY_IRCHECK=1). slots: after machine lowering
    # (machine_ir.py), where a load may give the opaque %slot of a payload it reads
    if i.op == "mach.addr":
        if len(i.a) != 2 or i.t != "%ptr" or i.s not in ["int", "%ptr", "%byte"] or i.x != "" or i.k not in [0, 1] or len(i.b) != 0:
            self.bad_ir(fn, b, "mach.addr needs a machine element type and inbounds flag")
        if i.a[0].t != "%ptr" or i.a[1].t != "int":
            self.bad_ir(fn, b, "mach.addr needs a machine pointer and int index")
        return
    load = i.op == "mach.load"
    if len(i.a) != (1 if load else 2) or i.x != "" or i.k != 0 or len(i.b) != 0:
        self.bad_ir(fn, b, f"{i.op} has invalid operands or extra metadata")
    if i.a[0].t != "%ptr":
        self.bad_ir(fn, b, f"{i.op} needs a machine pointer address")
    t = i.t if load else i.a[1].t
    if t == "" or t == "None" or (t.startswith("%") and t not in ["%ptr", "%byte", "%i32"] and not (slots and load and t == "%slot")) or t.startswith("*") or t == "#" or ((t == "T" or t == "K" or t == "V" or t == "S") and t not in self.classes):
        self.bad_ir(fn, b, f"{i.op} needs a machine storage value type")
    if (not load and i.t != "") or i.s not in ["", "length", "length.range", "bytes"] or (i.s == "length.range" and not load) or (i.s.startswith("length") and t != "int") or (i.s == "bytes" and t != "%byte"):
        self.bad_ir(fn, b, f"{i.op} has invalid value or memory metadata")
