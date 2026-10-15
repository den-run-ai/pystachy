"""Typed operations for compiler-owned machine storage and indexed addresses.

Native mem.load/store retain the stronger *<native> address contract. These
operations also cover closure environments, runtime headers and byte buffers.
"""
from __future__ import annotations
from src.pystachy_compiler.ir import Ins, Val


def gen_mload(self, t: str, p: str, metadata: str = "") -> str:
    i = Ins("mach.load", t, metadata)
    i.a = [Val(p, "%ptr")]
    self.put(i, 1)
    return f"%t{i.r[0]}"


def gen_mstore(self, t: str, v: str, p: str, metadata: str = "") -> None:
    i = Ins("mach.store", "", metadata)
    i.a = [Val(p, "%ptr"), Val(v, t)]
    self.add(i)


def gen_maddr(self, t: str, p: str, index: str, inbounds: bool = False) -> str:
    i = Ins("mach.addr", "%ptr", t)
    i.a = [Val(p, "%ptr"), Val(index, "int")]
    i.k = 1 if inbounds else 0
    self.put(i, 1)
    return f"%t{i.r[0]}"
