"""Compile a source file to WebAssembly from the compiler's finalized typed IR.

The textual IR and source entry points share the emitter's Module and all of its
lowering. This adapter reads the same declarations, instruction field names and
result registers directly, avoiding inspection snapshots on the source path.
"""
import os
import sys

from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.driver import compile_program, compiler_home, prefer_program_ffi, program_dirs
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import IFn, Ins, slot_register
from src.pystachy_compiler.lexer import host_text
from src.pystachy_compiler.specs import OPS
from wasm.tir_wasm import Block, ClassDecl, Const, Emitter, Func, Inst, Module, Operand, Refused


def instruction(i: Ins) -> Inst:
    out = Inst(i.op)
    out.res = [f"%t{n}" for n in i.r]
    out.args = [Operand(v.t, v.v) for v in i.a]
    out.targets = i.b
    out.t = i.t
    # OPS is also the text printer's schema for Ins.s, .k and .x. Emitter
    # operands never refer to its private lowering temporaries by name.
    for field in OPS[i.op].split("|")[4].split():
        if field == "t":
            continue
        key = field[2:]
        if field[0] == "s" and i.s != "":
            if key == "operator":
                out.operator = i.s
            else:
                out.fields[key] = i.s
        elif field[0] == "k" and i.k != 0:
            out.fields[key] = str(i.k)
        elif field[0] == "x" and i.x != "":
            out.fields[key] = i.x
    return out


def function(fn: IFn, closed: bool) -> Func:
    f = fn.f
    if fn.coro:
        raise Refused(f"{f.ll} is a generator")
    if fn.ps != [j for j in range(len(f.ptypes)) if f.ptypes[j] != "None"]:
        raise Refused(f"parameter ABI of {f.ll}")
    out = Func(f.ll)
    out.ptypes = f.ptypes
    out.ret = f.ret
    out.attrs["kind"] = f.node.kind
    if f.export:
        out.attrs["export"] = ""
    if f.extern:
        out.attrs["extern"] = ""
    if closed:
        out.attrs["closed"] = ""
    out.cold = fn.cold
    for slot in fn.slots:
        out.slots[slot_register(slot)] = slot.t
    for b in fn.blocks:
        if b.handler != "":
            raise Refused(f"block {b.label} has a handler (exceptions)")
        block = Block(b.label)
        block.code = [instruction(i) for i in b.code]
        out.blocks.append(block)
    return out


def wasm_module(gen: Gen) -> Module:
    if gen.pipeline.stage != "finalize" or gen.pipeline.active != "":
        raise Refused("typed IR is not finalized")
    # Tables which require hooks that the shared runtime cannot supply.
    if gen.eh:
        raise Refused("module attribute exceptions")
    if diagnostics.dynamic_program():
        raise Refused("module attribute dynamic")
    if diagnostics.int_program():
        raise Refused("module attribute promoting")
    if gen.gproto or gen.ext != "" or gen.rtmode:
        raise Refused("module requires generators, extension exports or runtime mode")
    if len(gen.ocls) + len(gen.ocmp) + len(gen.hcls) + len(gen.one) + len(gen.xobj) != 0:
        raise Refused("module requires object dispatch")
    if len(gen.rtdatas) != 0:
        raise Refused("module declaration rtdata")
    if len(gen.externs) != 0:
        raise Refused("module declaration extern")
    m = Module()
    m.attrs["complete"] = ""
    m.attrs["opts"] = "[" + " ".join(gen.opts) + "]"
    for name in gen.classes:
        ci = gen.classes[name]
        cd = ClassDecl(name)
        cd.ftypes = [ci.ftypes[field] for field in ci.fields]
        cd.nflag = ci.nflag
        cd.nbox = ci.nbox
        m.classes[name] = cd
    for k in range(1, len(gen.holes)):
        m.holes[k] = gen.holes[k]
    for g in gen.globs:
        m.globals[g.v] = g.t
        m.order.append(g.v)
    for d in gen.consts:
        c = Const(d.name, d.kind)
        c.text = d.text
        c.refs = d.refs
        c.items = [Operand(v.t, v.v) for v in d.items]
        m.consts.append(c)
    m.keykinds = gen.keykinds
    m.builtkinds = gen.builtkinds
    for fn in gen.fns:
        m.funcs.append(function(fn, fn.f.ll in gen.rdpass))
    return m


class WasmBackend:
    def __init__(self, fallback: bool):
        self.fallback = fallback
        self.output = bytearray()
        self.refusal = ""

    def lower(self, gen: Gen) -> str:
        # Publish results only once the retrying compile_program returns. If LLVM
        # requests a retry, the next attempt replaces this refusal and its output.
        self.refusal = ""
        try:
            self.output = Emitter(wasm_module(gen)).module()
        except Refused as exc:
            self.refusal = exc.what
            if self.fallback:
                return gen.lower_program()
        return ""


def main() -> None:
    if len(sys.argv) not in (3, 4):
        sys.stderr.write("usage: wasm_from_source.py SOURCE.py|- OUT.wasm|- [FALLBACK.ll]\n")
        sys.exit(2)
    sys.setrecursionlimit(diagnostics.MAXNEST * 40)
    from_stdin = sys.argv[1] == "-"
    diagnostics.SRC = "<codemode>.py" if from_stdin else sys.argv[1]
    dirs = program_dirs("" if from_stdin else diagnostics.SRC, compiler_home())
    prefer_program_ffi(dirs)
    if from_stdin:
        source = host_text(sys.stdin.read())
    else:
        with open(sys.argv[1], encoding=diagnostics.RAW) as f:
            source = f.read()
    backend = WasmBackend(len(sys.argv) == 4)
    llvm = compile_program(diagnostics.SRC, source, dirs, "", backend.lower)
    if backend.refusal != "":
        sys.stderr.write(f"tir_wasm: refused: {backend.refusal}\n")
        if backend.fallback:
            with open(sys.argv[3], "w", encoding=diagnostics.RAW) as fallback:
                fallback.write(llvm)
        sys.exit(3)
    data = bytes(backend.output)
    if sys.argv[2] == "-":
        at = 0
        while at < len(data):
            count = os.write(1, data[at:])
            if count == 0:
                raise OSError("short write to stdout")
            at += count
    else:
        with open(sys.argv[2], "wb") as output:
            output.write(data)


if __name__ == "__main__":
    main()
