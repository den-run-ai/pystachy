"""Typed operations for compiler-owned machine storage and indexed addresses.

Native mem.load/store retain the stronger &<native> address contract. These
operations also cover closure environments, runtime headers and byte buffers.
"""
from __future__ import annotations
from src.pystachy_compiler.ir import Blk, IFn, Ins, Val, tmpname
from src.pystachy_compiler.specs import CONTAINER_HEADERS, RTRECORDS, RT_TBAA
from src.pystachy_compiler.utils import RT_VARS


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
    # (machine_ir.py), where a load may give the opaque %slot of a payload it reads. A word may
    # hold a packed slot *T of a native T, and a store may write one as %slot
    if i.op == "mach.addr":
        record = i.s[4:] if i.s.startswith("rec.") else ""
        if len(i.a) != 2 or i.t != "%ptr" or (i.s not in ["int", "%ptr", "%byte", "%i32", "dyntype", "classrec", "list.header", "dict.header"] and record not in RTRECORDS) or i.x != "" or i.k not in [0, 1] or len(i.b) != 0:
            self.bad_ir(fn, b, "mach.addr needs a machine element type and inbounds flag")
        if i.a[0].t != "%ptr" or i.a[1].t != "int":
            self.bad_ir(fn, b, "mach.addr needs a machine pointer and int index")
        if record != "" and (not self.rtmode or i.a[1].v not in [str(j) for j in range(len(RTRECORDS[record].split()) + 1)]):
            # (a field of one of runtime.c's records, or one past the last: the record's size)
            self.bad_ir(fn, b, "mach.addr needs a field of the runtime record, in runtime mode")
        if i.s in ("list.header", "dict.header") and i.a[1].v not in [str(k) for k in range(len(CONTAINER_HEADERS[i.s[:-7]]))]:
            self.bad_ir(fn, b, "mach.addr needs a valid container header field index")
        if i.s == "dyntype" and i.a[1].v not in ["2", "3", "5"]:
            self.bad_ir(fn, b, "mach.addr needs a DynType name, class or flags field")
        if i.s == "classrec" and i.a[1].v != "3":
            self.bad_ir(fn, b, "mach.addr needs the reflection record flags field")
        return
    load = i.op == "mach.load"
    if len(i.a) != (1 if load else 2) or i.x != "" or i.k != 0 or len(i.b) != 0:
        self.bad_ir(fn, b, f"{i.op} has invalid operands or extra metadata")
    if i.a[0].t != "%ptr":
        self.bad_ir(fn, b, f"{i.op} needs a machine pointer address")
    t = i.t if load else i.a[1].t
    if t == "" or t == "None" or (t.startswith("%") and t not in ["%ptr", "%byte", "%i32"] and not (t == "%slot" and (slots or not load))) or (t.startswith("*") and (t == "*" or t[1:2] in ["%", "*", "&", "#"])) or t.startswith("&") or t == "#" or (t in RT_VARS and t not in self.classes):
        self.bad_ir(fn, b, f"{i.op} needs a machine storage value type")
    if (not load and i.t != "") or (i.s not in ["", "length", "length.range", "bytes"] and not (self.rtmode and i.s in RT_TBAA)) or (i.s == "length.range" and not load) or (i.s.startswith("length") and t != "int") or (i.s == "bytes" and t != "%byte"):
        self.bad_ir(fn, b, f"{i.op} has invalid value or memory metadata")
    if (i.s == "rt.word" or i.s == "rt.int") and t != "int" or (i.s == "rt.ptr" and t != "%ptr"):
        self.bad_ir(fn, b, f"{i.op} has a runtime memory tag of another type")
